# 🏗️ 실서비스 전환 설계 문서

> 텍사스 홀덤 실시간 멀티플레이 — 프로토타입에서 실서비스로.
> 작성일: 2026-11-03 · 대상 커밋: `poker_engine.py` / `app.py` 현재 구조 기준

---

## 1. 목표와 범위

### 목표
- 현재 "단일 Streamlit 프로세스 메모리"에 묶인 멀티플레이 상태를 **외부화·영속화**하여, 서버 재시작과 다중 인스턴스에서도 게임이 유지·공유되게 한다.
- 게임 로직(`poker_engine.py`)의 **순수 함수 특성을 보존**하여 재작성 없이 재사용한다.

### 범위 (단계별)
| 단계 | 내용 | 본 문서에서 |
| :-- | :-- | :-- |
| **1단계** | Redis로 상태 외부화 + 분산 락 | **상세 설계** |
| **2단계** | WebSocket 실시간 푸시 | 설계 개요 |
| **3단계** | 계정·영속 DB·보안 | 방향 제시 |
| **4단계** | 컨테이너·운영·확장 | 방향 제시 |

핵심 원칙: **각 단계는 독립적으로 배포 가능해야 한다.** 1단계만 적용해도 소규모 실서비스가 가능하다.

---

## 2. 현재 아키텍처 (As-Is)

```
┌───────────────────────────────────────────────┐
│  Streamlit 프로세스 (단일)                      │
│                                                │
│  @st.cache_resource get_server()               │
│    ├─ rooms: { code → room_dict }   ← 인메모리   │
│    └─ lock: threading.Lock          ← 프로세스 락 │
│                                                │
│  app.py (UI)                                   │
│    with LOCK:                                  │
│      room = ROOMS.get(code)                    │
│      PE.player_action(room, ...)   ← 상태 변이   │
│      snap = deepcopy(room)          ← 렌더용 복제 │
│    st.rerun() / st_autorefresh(1.5s)           │
│                                                │
│  poker_engine.py (순수 로직, 락/IO 없음)         │
└───────────────────────────────────────────────┘
```

### 핵심 특성 (유지해야 할 좋은 설계)
- **엔진은 순수하다:** `poker_engine.py`는 `room` 딕셔너리를 받아 제자리(in-place) 변이하는 순수 함수 모음. 네트워크·락·IO를 모른다. → 저장소만 바꾸면 그대로 재사용 가능.
- **단일 변이 진입점:** 상태를 바꾸는 함수는 모두 `with LOCK:` 안에서만 호출된다(`new_room`/`join_room`/`start_hand`/`player_action`/`rebuy`/`reset_tournament`/`leave_room`/`enforce_timeout`).
- **버전 카운터 존재:** `room["version"]` 이 변이마다 `_bump()`으로 증가 → 낙관적 동시성 제어(OCC)에 활용 가능.

### 변이 함수 전체 목록 (락 보호 대상)
`new_room`, `join_room`, `leave_room`, `start_hand`, `player_action`, `rebuy`, `reset_tournament`, `enforce_timeout`, (내부적으로 `auto_advance`/`fill_with_ai`/`_resolve_showdown` 등 호출).

읽기 전용: `seat_of_token`, `playing_order`, `contenders`, `get_positions`, `time_left`, `occupied_seats`, `human_seats`.

---

## 3. 문제점

| # | 문제 | 영향 |
| :- | :-- | :-- |
| P1 | 상태가 프로세스 메모리에만 존재 | 서버 재시작 시 모든 방 소멸 |
| P2 | `threading.Lock`은 프로세스 내부 전용 | 인스턴스 2개↑로 스케일아웃 시 상태 분리·락 무력화 |
| P3 | 폴링(`st_autorefresh` 1.5초) | 지연·불필요한 서버 부하, 즉시성 부족 |
| P4 | 영속 저장 없음 | 전적·칩·랭킹 등 데이터 보존 불가 |
| P5 | 서버 측 공정성/보안 미흡 | 입력 검증·레이트리밋·치팅 방지 부재 |

> 1단계는 **P1, P2**를 해결한다. P3는 2단계, P4·P5는 3단계.

---

## 4. 목표 아키텍처 (To-Be, 1단계)

```
┌─────────────┐   ┌─────────────┐        ┌──────────────┐
│ Streamlit #1 │   │ Streamlit #2 │  ...   │   Redis       │
│  app.py      │   │  app.py      │        │               │
│   │RoomStore  │──▶│   │RoomStore  │─────▶ │ room:{code}   │  (JSON 문자열)
│   └분산 락    │   │   └분산 락    │       │ lock:{code}   │  (SET NX PX)
└─────────────┘   └─────────────┘        │ rooms:index   │  (SET, TTL 관리)
                                          └──────────────┘
```

- 여러 Streamlit 인스턴스가 **같은 Redis**를 공유 → P1·P2 해소.
- `poker_engine.py`는 **수정하지 않는다.** `room` 딕셔너리를 Redis에서 로드→변이→저장하는 **`RoomStore` 추상화**만 새로 넣는다.

---

## 5. 1단계 상세 설계 — Redis 상태 외부화

### 5.1 저장소 추상화 (`store.py` 신규)

목적: `ROOMS`(dict)와 `LOCK`(threading.Lock) 사용부를 **인터페이스 뒤로 숨겨**, 인메모리/Redis 구현을 교체 가능하게 한다.

```python
# store.py  (신규)
from abc import ABC, abstractmethod
from contextlib import contextmanager

class RoomStore(ABC):
    @abstractmethod
    def get(self, code) -> dict | None: ...
    @abstractmethod
    def save(self, room: dict) -> None: ...
    @abstractmethod
    def delete(self, code) -> None: ...
    @abstractmethod
    def list_codes(self) -> list[str]: ...
    @abstractmethod
    @contextmanager
    def lock(self, code): ...        # 방 단위 분산 락
```

#### (a) 인메모리 구현 — 현재 동작 보존 (로컬/테스트용)
```python
class MemoryRoomStore(RoomStore):
    def __init__(self):
        self._rooms, self._lock = {}, threading.Lock()
    def get(self, code):   return self._rooms.get(code)
    def save(self, room):  self._rooms[room["code"]] = room
    def delete(self, code): self._rooms.pop(code, None)
    def list_codes(self):  return list(self._rooms)
    @contextmanager
    def lock(self, code):
        with self._lock:   # 단순화: 전역 락 (현재와 동일)
            yield
```

#### (b) Redis 구현 — 실서비스용
```python
import json, redis
from redis.lock import Lock as RedisLock

class RedisRoomStore(RoomStore):
    ROOM = "holdem:room:{}"          # 값: room JSON
    INDEX = "holdem:rooms:index"     # 값: 활성 방 코드 SET
    TTL = 60 * 60 * 6                # 방 6시간 무활동 시 만료

    def __init__(self, url):
        self.r = redis.Redis.from_url(url, decode_responses=True)

    def get(self, code):
        raw = self.r.get(self.ROOM.format(code))
        return json.loads(raw) if raw else None

    def save(self, room):
        code = room["code"]
        self.r.set(self.ROOM.format(code), json.dumps(room), ex=self.TTL)
        self.r.sadd(self.INDEX, code)

    def delete(self, code):
        self.r.delete(self.ROOM.format(code))
        self.r.srem(self.INDEX, code)

    def list_codes(self):
        return list(self.r.smembers(self.INDEX))

    @contextmanager
    def lock(self, code):
        # 방 단위 분산 락: 동시 변이 직렬화 (blocking, 자동 만료로 데드락 방지)
        with RedisLock(self.r, f"holdem:lock:{code}", timeout=10, blocking_timeout=5):
            yield
```

> **직렬화 주의:** `room` 안에는 카드가 문자열(`"As"`)로 저장돼 JSON 직렬화가 그대로 된다. `treys`의 `Card` 정수나 객체를 room에 넣지 않는 현재 설계가 유지되어야 한다. (현재 엔진은 문자열 카드만 저장하므로 OK.)

### 5.2 변이 트랜잭션 패턴

모든 상태 변경을 **load → mutate → save** 를 락 안에서 수행하는 헬퍼로 통일한다.

```python
# app.py 측 헬퍼
def mutate(code, fn):
    """fn(room) 안에서 PE.* 변이 함수를 호출. 락·로드·저장을 캡슐화."""
    with STORE.lock(code):
        room = STORE.get(code)
        if room is None:
            return None
        fn(room)                 # 예: lambda r: PE.player_action(r, seat, "call")
        STORE.save(room)
        return room
```

#### Before → After (app.py 호출부 예시)
```python
# Before (인메모리 + threading.Lock)
with LOCK:
    r = ROOMS.get(room_code)
    if r:
        PE.player_action(r, my_seat, "call")
st.rerun()

# After (저장소 추상화)
mutate(room_code, lambda r: PE.player_action(r, my_seat, "call"))
st.rerun()
```

렌더 시 스냅샷:
```python
# Before:  with LOCK: PE.enforce_timeout(room); snap = deepcopy(room)
# After:
mutate(room_code, PE.enforce_timeout)   # 타임아웃도 변이이므로 락 안에서
snap = STORE.get(room_code)             # 읽기 전용 스냅샷 (deepcopy 불필요: Redis가 사본 반환)
```

### 5.3 서버 부트스트랩 (환경변수로 구현 선택)

```python
# app.py 상단
@st.cache_resource
def get_store():
    url = os.getenv("REDIS_URL")
    return RedisRoomStore(url) if url else MemoryRoomStore()

STORE = get_store()
```
- `REDIS_URL` 미설정 → 기존 인메모리 동작(로컬 개발·CI).
- 설정 시 → Redis 공유. **코드 한 줄도 분기 없이** 실/로컬 전환.

### 5.4 동시성 모델 결정

| 방식 | 설명 | 채택 |
| :-- | :-- | :-- |
| **A. 방 단위 분산 락** | `lock:{code}` 획득 후 load-mutate-save | ✅ **채택** (단순·충분, 방 간 경합 없음) |
| B. 낙관적 OCC | `room["version"]` 비교 후 CAS, 충돌 시 재시도 | 대안 (락 경합 큰 초고빈도일 때) |

> 홀덤은 "한 방에서 한 번에 한 명만 액션"하므로 방 단위 락으로 충분하다. `version` 필드는 2단계(변경 감지 푸시)에서 활용한다.

### 5.5 방 생명주기 / 만료

- `save()` 마다 TTL 6시간 갱신 → 무활동 방 자동 정리(현재는 사람이 다 나가면 삭제하는 로직 유지).
- `list_codes()` + 각 방 `enforce_timeout` 를 주기적으로 도는 **정리 워커**(2단계에서 백그라운드 태스크로) 고려.

### 5.6 마이그레이션 절차

1. `store.py` 추가, `MemoryRoomStore`로 먼저 교체(**동작 동일, 리스크 0**) → 회귀 테스트.
2. `RedisRoomStore` 추가, `REDIS_URL` 세팅해 스테이징 검증.
3. `requirements.txt` 에 `redis>=5.0` 추가.
4. 배포. (기존 방 데이터 마이그레이션은 불필요 — 휘발성 세션)

---

## 6. 2단계 — 실시간 푸시 (설계 개요)

- **문제(P3):** 폴링은 지연·부하. → **WebSocket**으로 교체.
- **현실적 경로:** 게임 서버를 **FastAPI + WebSocket**로 분리.
  - 클라이언트가 방에 구독(subscribe).
  - 변이 발생 시 Redis **Pub/Sub**(`channel: room:{code}`)로 모든 인스턴스에 통지 → 각 인스턴스가 구독자에게 push.
  - `room["version"]`을 payload에 실어 **클라이언트가 변경분만 반영**.
- Streamlit은 이 시점에서 **데모/관리 콘솔**로 역할 축소하고, 플레이어 UI는 React/모바일로 신규 구현 권장.
- 전환 비용을 줄이려면 `poker_engine.py`를 그대로 FastAPI 서버의 코어로 임포트.

```
Client(WS) ─▶ FastAPI ─▶ RoomStore(Redis) ─┐
      ▲                                      │ Pub/Sub
      └────────── push ◀──── 모든 인스턴스 ◀──┘
```

---

## 7. 3단계 — 계정·영속·보안 (방향)

- **인증:** 세션 토큰(`uuid`) → OAuth/계정. 재접속 시 좌석 소유권 복원.
- **영속 DB(PostgreSQL):** 유저, 게임 결과, 핸드 히스토리, 칩/랭킹. Redis는 "진행 중 상태", DB는 "영속 기록"으로 역할 분리.
- **공정성/보안:**
  - 셔플은 **서버에서만**(현재 `start_hand`의 `random.shuffle`은 서버측 → 유지). 홀 카드는 **소유자에게만** 전송(현재 렌더는 `mine or revealed`로 필터 → WS에서도 좌석별 개인화 payload 필요).
  - 입력 검증(이미 엔진이 불법 액션 방지), **레이트리밋**, 액션 서버 재검증, 감사 로그.

---

## 8. 4단계 — 운영·확장 (방향)

- **컨테이너화:** Dockerfile + compose(app, redis, db). 환경변수로 설정 주입.
- **스케일:** 무상태(stateless) 인스턴스 + Redis/DB 공유 → 수평 확장. 방이 많아지면 **코드 해시 기반 샤딩**.
- **관측성:** 구조적 로깅, 메트릭(활성 방 수·턴 지연·에러율), 헬스체크.

---

## 9. API 계약 (불변)

`poker_engine.py`의 시그니처는 **1~2단계 내내 변경하지 않는다.** 저장소/전송 계층만 바뀐다.

- 변이: `fn(room, ...)` → `room` 제자리 변이 + `_bump()`.
- 호출 측 책임: 로드 → 락 → 변이 → 저장(+버전 전파).

이 계약을 지키면 Streamlit·FastAPI 어느 호스트에서도 동일 엔진을 재사용할 수 있다.

---

## 10. 테스트 전략

| 수준 | 대상 | 방법 |
| :-- | :-- | :-- |
| 단위 | `poker_engine` 규칙(블라인드·사이드팟·올인·타임아웃) | 기존 순수 함수에 픽스처 room 주입 |
| 통합 | `RoomStore` 양 구현 | 동일 테스트를 Memory/Redis 둘 다 통과(`fakeredis` 활용) |
| 동시성 | 방 단위 락 | 두 스레드가 같은 방에 동시 액션 → 직렬화·불변식 검증 |
| 회귀 | 1단계 Memory 교체 | 교체 전후 동작 동일성 |

---

## 11. 리스크 & 결정 로그

| 항목 | 결정 | 근거 |
| :-- | :-- | :-- |
| 직렬화 포맷 | JSON | room이 원시 타입·문자열 카드만 포함, 디버깅 용이 |
| 락 방식 | 방 단위 Redis 락 | 단순·충분, 데드락은 `timeout`으로 방지 |
| 엔진 수정 | 없음 | 순수성 유지가 재사용의 핵심 |
| Streamlit 존치 | 1단계 유지, 2단계부터 역할 축소 | 점진적 전환·리스크 최소화 |
| TTL | 6시간 | 세션성 게임, 무활동 방 자동 회수 |

---

## 12. 구현 체크리스트 (1단계)

- [ ] `store.py`: `RoomStore` / `MemoryRoomStore` / `RedisRoomStore`
- [ ] `app.py`: `get_store()`, `mutate()` 헬퍼 도입
- [ ] `app.py`: `ROOMS`/`LOCK` 직접 참조 → `STORE`/`mutate`로 전면 교체 (변이 7개 지점 + 렌더 스냅샷)
- [ ] `requirements.txt`: `redis>=5.0`, (테스트) `fakeredis`
- [ ] 환경변수 문서화: `REDIS_URL`
- [ ] 통합 테스트: Memory/Redis 동일 통과
- [ ] 스테이징에서 2인스턴스 + 공유 Redis로 방 공유 검증
