"""
서버 권위(authoritative) 텍사스 홀덤 멀티플레이 엔진.

Streamlit UI와 완전히 분리된 순수 파이썬 모듈이다.
모든 게임 상태는 하나의 `room` 딕셔너리에 담기며, 이 딕셔너리는
서버 메모리(여러 사용자 세션이 공유)에 저장된다.

호출 측(app.py)은 반드시 threading.Lock 을 잡은 상태에서
mutate 계열 함수(create_room/join_room/start_hand/player_action/...)를
호출해야 한다. 이 모듈 자체는 락을 다루지 않는다.
"""

import random
import time

RANKS = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"]
SUITS = ["s", "h", "d", "c"]

# 한 플레이어가 자기 턴을 방치할 때 자동 처리(폴드/체크)까지의 시간(초)
TURN_SECONDS = 60


def _evaluator():
    # treys 평가기를 지연 로딩 (모듈 import 비용 최소화)
    from treys import Evaluator
    if not hasattr(_evaluator, "_inst"):
        _evaluator._inst = Evaluator()
    return _evaluator._inst


def make_deck():
    return [f"{r}{s}" for r in RANKS for s in SUITS]


def gen_code(k=6):
    import string
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=k))


# ==========================================
# 좌석 / 방 생성
# ==========================================
def _empty_seat(i):
    return {
        "idx": i,
        "kind": "EMPTY",      # EMPTY | HUMAN | AI
        "token": None,         # HUMAN 좌석의 세션 토큰
        "name": "(빈자리)",
        "chips": 0,
        "rebuys": 0,
        "eliminated": False,
        "in_hand": False,      # 이번 핸드에 참여(딜) 되었는가
        "folded": True,
        "hole": [],
        "bet": 0,              # 현재 스트리트 베팅액
        "contrib": 0,          # 이번 핸드 누적 기여액
        "last_action": "",     # 최근 액션 라벨 (UI 표시용)
        "sitting_out": False,  # 핸드 도중 합류 → 다음 핸드부터 참여
    }


def new_room(config, host_token, host_name):
    """방 생성. 0번 좌석을 방장(HUMAN)으로 채운다."""
    max_p = int(config["max_players"])
    seats = [_empty_seat(i) for i in range(max_p)]
    seats[0].update({
        "kind": "HUMAN",
        "token": host_token,
        "name": host_name,
        "chips": int(config["start_chips"]),
        "rebuys": int(config["rebuys"]),
        "eliminated": False,
        "folded": True,
    })
    room = {
        "code": config.get("code") or gen_code(),
        "config": {
            "max_players": max_p,
            "start_chips": int(config["start_chips"]),
            "rebuys": int(config["rebuys"]),
            "bb": int(config["bb"]),
            "sb": int(config["bb"]) // 2,
        },
        "host_token": host_token,
        "seats": seats,
        "stage": "LOBBY",         # LOBBY | PREFLOP | FLOP | TURN | RIVER | SHOWDOWN | IDLE
        "dealer_seat": 0,
        "active_seat": -1,
        "pot": 0,
        "current_max_bet": 0,
        "board": [],
        "deck": [],
        "acted": [],
        "log": [],
        "result": None,
        "hand_no": 0,
        "version": 0,
        "turn_deadline": 0.0,
        "winner_seat": None,       # 토너먼트 최종 우승 좌석
    }
    return room


def _bump(room):
    room["version"] += 1


def _log(room, msg):
    room["log"].append(msg)
    if len(room["log"]) > 200:
        room["log"] = room["log"][-200:]


# ==========================================
# 좌석 조회 헬퍼
# ==========================================
def seat_of_token(room, token):
    for s in room["seats"]:
        if s["kind"] == "HUMAN" and s["token"] == token:
            return s["idx"]
    return None


def human_seats(room):
    return [s for s in room["seats"] if s["kind"] == "HUMAN"]


def occupied_seats(room):
    return [s for s in room["seats"] if s["kind"] != "EMPTY"]


def playing_order(room):
    """이번 핸드에 자리한(비어있지 않고 탈락하지 않은) 좌석 인덱스 순서."""
    return [s["idx"] for s in room["seats"] if s["kind"] != "EMPTY" and not s["eliminated"]]


def contenders(room):
    """현재 핸드에서 아직 승부에 남아있는 좌석 인덱스."""
    return [s["idx"] for s in room["seats"]
            if s["in_hand"] and not s["folded"] and not s["eliminated"]]


# ==========================================
# 입장 / 퇴장
# ==========================================
def join_room(room, token, name):
    """빈 좌석에 HUMAN 합류. 이미 앉아있으면 그 좌석 반환.
    빈 좌석이 없으면 살아있는 AI 좌석을 인계(스택 승계)한다. 완전히 차면 None."""
    existing = seat_of_token(room, token)
    if existing is not None:
        room["seats"][existing]["name"] = name
        return existing
    # 1) 빈 좌석 우선 — 무작위로 배정 (입장 순서와 좌석 번호가 고정되지 않도록)
    empty_seats = [s for s in room["seats"] if s["kind"] == "EMPTY"]
    if empty_seats:
        s = random.choice(empty_seats)
        s.update({
            "kind": "HUMAN",
            "token": token,
            "name": name,
            "chips": room["config"]["start_chips"],
            "rebuys": room["config"]["rebuys"],
            "eliminated": False,
            "folded": True,
            "in_hand": False,
            "sitting_out": (room["stage"] not in ("LOBBY", "IDLE", "SHOWDOWN")),
            "hole": [], "bet": 0, "contrib": 0, "last_action": "",
        })
        _log(room, f"👋 {name} 님이 {s['idx']+1}번 좌석으로 입장했습니다.")
        _bump(room)
        return s["idx"]
    # 2) 빈 좌석이 없으면 살아있는 AI 좌석을 무작위로 인계 (현재 스택/핸드 상태 승계)
    ai_seats = [s for s in room["seats"] if s["kind"] == "AI" and not s["eliminated"]]
    if ai_seats:
        s = random.choice(ai_seats)
        s["kind"] = "HUMAN"
        s["token"] = token
        s["name"] = name
        _log(room, f"🙋 {name} 님이 {s['idx']+1}번 봇(AI) 좌석을 인계했습니다.")
        _bump(room)
        return s["idx"]
    return None


def leave_room(room, token):
    idx = seat_of_token(room, token)
    if idx is None:
        return
    s = room["seats"][idx]
    nm = s["name"]
    # 핸드 진행 중이면 폴드 처리
    if s["in_hand"] and not s["folded"]:
        s["folded"] = True
        s["last_action"] = "LEAVE"
    room["seats"][idx] = _empty_seat(idx)
    _log(room, f"🚪 {nm} 님이 퇴장했습니다.")
    # 방장이 나가면 다른 HUMAN 에게 방장 위임
    if room["host_token"] == token:
        others = human_seats(room)
        room["host_token"] = others[0]["token"] if others else None
    _bump(room)
    # 핸드 중이었다면 진행을 이어서 정리
    if room["stage"] not in ("LOBBY", "IDLE", "SHOWDOWN"):
        auto_advance(room)


def fill_with_ai(room):
    """남은 빈 좌석을 AI 로 채운다 (핸드 시작 직전 호출)."""
    cfg = room["config"]
    ai_n = 0
    for s in room["seats"]:
        if s["kind"] == "EMPTY":
            ai_n += 1
            s.update({
                "kind": "AI",
                "token": None,
                "name": f"AI {s['idx']+1}",
                "chips": cfg["start_chips"],
                "rebuys": cfg["rebuys"],
                "eliminated": False,
                "folded": True,
                "in_hand": False,
                "sitting_out": False,
                "hole": [], "bet": 0, "contrib": 0, "last_action": "",
            })
    if ai_n:
        _bump(room)


# ==========================================
# 포지션
# ==========================================
def get_positions(dealer_seat, order):
    n = len(order)
    if n < 2:
        return (order[0] if order else 0,) * 3
    if dealer_seat in order:
        d = order.index(dealer_seat)
    else:
        d = 0
    if n == 2:
        sb = order[d]
        bb = order[(d + 1) % 2]
        utg = sb
    else:
        sb = order[(d + 1) % n]
        bb = order[(d + 2) % n]
        utg = order[(d + 3) % n]
    return sb, bb, utg


def _next_active(room, cur):
    """cur 다음으로 '자리한(탈락X, 비어있지않음)' 좌석."""
    n = room["config"]["max_players"]
    order_set = set(playing_order(room))
    for step in range(1, n + 1):
        nxt = (cur + step) % n
        if nxt in order_set:
            return nxt
    return cur


# ==========================================
# 핸드 시작
# ==========================================
def start_hand(room):
    cfg = room["config"]
    fill_with_ai(room)

    # 리바이 / 탈락 처리
    for s in room["seats"]:
        if s["kind"] == "EMPTY" or s["eliminated"]:
            continue
        if s["chips"] <= 0:
            if s["rebuys"] > 0:
                s["chips"] = cfg["start_chips"]
                s["rebuys"] -= 1
                _log(room, f"🔄 {s['name']} 리바이 (남은 {s['rebuys']}회)")
            else:
                s["eliminated"] = True
                _log(room, f"💀 {s['name']} 탈락")

    order = playing_order(room)
    if len(order) < 2:
        # 토너먼트 종료
        room["stage"] = "IDLE"
        room["active_seat"] = -1
        room["winner_seat"] = order[0] if order else None
        if room["winner_seat"] is not None:
            _log(room, f"🏆 {room['seats'][room['winner_seat']]['name']} 최종 우승!")
        _bump(room)
        return

    # 딜러 버튼 회전
    if room["hand_no"] == 0:
        # 첫 핸드의 딜러(=선·블라인드 순서 기준)를 무작위로 정해 턴 순서가 고정되지 않도록 한다.
        room["dealer_seat"] = random.choice(order)
    else:
        if room["dealer_seat"] in order:
            di = order.index(room["dealer_seat"])
            room["dealer_seat"] = order[(di + 1) % len(order)]
        else:
            room["dealer_seat"] = order[0]

    # 덱 준비 & 딜
    deck = make_deck()
    random.shuffle(deck)

    for s in room["seats"]:
        s["bet"] = 0
        s["contrib"] = 0
        s["last_action"] = ""
        if s["kind"] != "EMPTY" and not s["eliminated"]:
            s["in_hand"] = True
            s["folded"] = False
            s["sitting_out"] = False
            s["hole"] = [deck.pop(), deck.pop()]
        else:
            s["in_hand"] = False
            s["folded"] = True
            s["hole"] = []

    room["deck"] = deck
    room["board"] = []
    room["pot"] = 0
    room["acted"] = []
    room["result"] = None
    room["stage"] = "PREFLOP"
    room["hand_no"] += 1
    room["winner_seat"] = None

    sb_pos, bb_pos, utg = get_positions(room["dealer_seat"], order)

    _post_blind(room, sb_pos, cfg["sb"], "SB")
    _post_blind(room, bb_pos, cfg["bb"], "BB")
    room["current_max_bet"] = cfg["bb"]
    room["active_seat"] = utg

    _log(room, f"🃏 핸드 #{room['hand_no']} 시작 (딜러: {room['seats'][room['dealer_seat']]['name']})")
    _touch_turn(room)
    _bump(room)
    auto_advance(room)


def _post_blind(room, seat_idx, amount, tag):
    s = room["seats"][seat_idx]
    val = min(amount, s["chips"])
    s["chips"] -= val
    s["bet"] = val
    s["contrib"] += val
    room["pot"] += val
    s["last_action"] = f"{tag} {val}"


def _touch_turn(room):
    room["turn_deadline"] = time.time() + TURN_SECONDS


# ==========================================
# 베팅 라운드 진행
# ==========================================
def _should_advance_street(room):
    cs = contenders(room)
    if len(cs) <= 1:
        return False  # 무혈입성은 별도 처리
    can_act = [i for i in cs if room["seats"][i]["chips"] > 0]
    if not can_act:
        return True
    if len(can_act) == 1:
        i = can_act[0]
        s = room["seats"][i]
        if s["bet"] < room["current_max_bet"] and i not in room["acted"]:
            return False  # 혼자 남았지만 콜/폴드 결정이 남음
        return True
    return all((i in room["acted"]) and room["seats"][i]["bet"] == room["current_max_bet"]
               for i in can_act)


def auto_advance(room):
    """AI 턴을 자동 처리하고, 베팅 라운드/스트리트를 전진시킨다.
    사람(HUMAN)의 결정이 필요한 지점에서 멈춘다."""
    guard = 0
    while guard < 2000:
        guard += 1
        if room["stage"] in ("LOBBY", "IDLE", "SHOWDOWN"):
            return

        cs = contenders(room)
        if len(cs) <= 1:
            _award_uncontested(room, cs[0] if cs else None)
            return

        if _should_advance_street(room):
            _advance_street(room)
            continue

        cur = room["active_seat"]
        s = room["seats"][cur]

        if s["eliminated"] or (not s["in_hand"]) or s["folded"] or s["chips"] == 0:
            if cur not in room["acted"]:
                room["acted"].append(cur)
            room["active_seat"] = _next_active(room, cur)
            continue

        if s["kind"] == "HUMAN":
            _touch_turn(room)
            return  # 사람 입력 대기

        # AI 자동 액션
        _ai_act(room, cur)
        room["active_seat"] = _next_active(room, cur)


def _advance_street(room):
    for s in room["seats"]:
        s["bet"] = 0
    room["current_max_bet"] = 0
    room["acted"] = []

    order = playing_order(room)
    if len(order) == 2:
        _, bb_pos, _ = get_positions(room["dealer_seat"], order)
        room["active_seat"] = bb_pos
    else:
        sb_pos, _, _ = get_positions(room["dealer_seat"], order)
        room["active_seat"] = sb_pos

    stage = room["stage"]
    if stage == "PREFLOP":
        room["board"] = [room["deck"].pop() for _ in range(3)]
        room["stage"] = "FLOP"
        _log(room, f"🂠 플랍 오픈: {' '.join(room['board'])}")
    elif stage == "FLOP":
        room["board"].append(room["deck"].pop())
        room["stage"] = "TURN"
        _log(room, f"🂠 턴: {room['board'][-1]}")
    elif stage == "TURN":
        room["board"].append(room["deck"].pop())
        room["stage"] = "RIVER"
        _log(room, f"🂠 리버: {room['board'][-1]}")
    elif stage == "RIVER":
        _resolve_showdown(room)
    _touch_turn(room)
    _bump(room)


# ==========================================
# 액션 적용 (사람/AI 공통 하위 로직)
# ==========================================
def _apply_fold(room, idx):
    s = room["seats"][idx]
    s["folded"] = True
    s["last_action"] = "Fold"
    if idx not in room["acted"]:
        room["acted"].append(idx)
    _log(room, f"🏳️ {s['name']} 폴드")


def _apply_check(room, idx):
    s = room["seats"][idx]
    s["last_action"] = "Check"
    if idx not in room["acted"]:
        room["acted"].append(idx)
    _log(room, f"🔵 {s['name']} 체크")


def _apply_call(room, idx):
    s = room["seats"][idx]
    need = room["current_max_bet"] - s["bet"]
    pay = min(need, s["chips"])
    s["chips"] -= pay
    s["bet"] += pay
    s["contrib"] += pay
    room["pot"] += pay
    allin = " (ALL IN)" if s["chips"] == 0 else ""
    s["last_action"] = f"Call {pay}{allin}"
    if idx not in room["acted"]:
        room["acted"].append(idx)
    _log(room, f"🟢 {s['name']} 콜 {pay}{allin}")


def _apply_raise(room, idx, to_add):
    """to_add = 이번 턴 추가로 지출하는 칩(콜분 포함)."""
    s = room["seats"][idx]
    to_add = min(to_add, s["chips"])
    s["chips"] -= to_add
    s["bet"] += to_add
    s["contrib"] += to_add
    room["pot"] += to_add
    room["current_max_bet"] = max(room["current_max_bet"], s["bet"])
    allin = " (ALL IN)" if s["chips"] == 0 else ""
    s["last_action"] = f"Raise +{to_add}{allin}"
    room["acted"] = [idx]  # 레이즈 → 나머지 재행동 필요
    _log(room, f"🔴 {s['name']} 레이즈 +{to_add}{allin}")


# ==========================================
# 사람 액션 진입점
# ==========================================
def player_action(room, idx, action, amount=0):
    """action: 'fold'|'check'|'call'|'raise'|'allin'. amount=raise 시 추가 지출 칩."""
    if room["stage"] in ("LOBBY", "IDLE", "SHOWDOWN"):
        return False, "지금은 액션할 수 없습니다."
    if room["active_seat"] != idx:
        return False, "당신의 차례가 아닙니다."
    s = room["seats"][idx]
    if s["folded"] or s["eliminated"] or not s["in_hand"]:
        return False, "액션할 수 없는 상태입니다."

    need = room["current_max_bet"] - s["bet"]

    if action == "fold":
        _apply_fold(room, idx)
    elif action == "check":
        if need > 0:
            return False, "체크할 수 없습니다 (콜 필요)."
        _apply_check(room, idx)
    elif action == "call":
        if need <= 0:
            _apply_check(room, idx)
        else:
            _apply_call(room, idx)
    elif action == "raise":
        min_add = need + room["config"]["bb"]
        add = int(amount)
        if add < min_add:
            add = min_add
        add = min(add, s["chips"])
        _apply_raise(room, idx, add)
    elif action == "allin":
        _apply_raise(room, idx, s["chips"])
    else:
        return False, "알 수 없는 액션."

    room["active_seat"] = _next_active(room, idx)
    _bump(room)
    auto_advance(room)
    return True, "ok"


# ==========================================
# AI 의사결정
# ==========================================
def _ai_act(room, idx):
    s = room["seats"][idx]
    bb = room["config"]["bb"]
    need = room["current_max_bet"] - s["bet"]
    rnd = random.random()

    if need > 0:
        if rnd < 0.18 and s["chips"] > need + bb:
            _apply_raise(room, idx, need + bb)
        elif rnd < 0.32:
            _apply_fold(room, idx)
        else:
            _apply_call(room, idx)
    else:
        if rnd < 0.15 and s["chips"] >= bb:
            _apply_raise(room, idx, bb)
        else:
            _apply_check(room, idx)


# ==========================================
# 쇼다운 / 분배
# ==========================================
def _award_uncontested(room, winner_idx):
    payouts = [0] * room["config"]["max_players"]
    contribs = [s["contrib"] for s in room["seats"]]
    if winner_idx is not None:
        payouts[winner_idx] = room["pot"]
        room["seats"][winner_idx]["chips"] += room["pot"]
        _log(room, f"🎉 {room['seats'][winner_idx]['name']} 무혈입성 (+{room['pot']} 칩)")
    room["result"] = {
        "type": "fold",
        "payouts": payouts,
        "contribs": contribs,
        "pot_rows": [],
        "revealed": [],  # 전원 폴드는 패를 공개하지 않는다
        "msg": f"{room['seats'][winner_idx]['name']} 승리" if winner_idx is not None else "핸드 종료",
    }
    room["pot"] = 0
    room["stage"] = "IDLE"
    room["active_seat"] = -1
    _bump(room)


def _resolve_showdown(room):
    from treys import Card
    ev = _evaluator()
    max_p = room["config"]["max_players"]
    board_treys = [Card.new(c) for c in room["board"]]

    contribs = [s["contrib"] for s in room["seats"]]
    folded = [s["folded"] or s["eliminated"] or not s["in_hand"] for s in room["seats"]]

    scores = {}
    for i, s in enumerate(room["seats"]):
        if not folded[i] and len(s["hole"]) == 2:
            scores[i] = ev.evaluate(board_treys, [Card.new(c) for c in s["hole"]])

    caps = sorted(set(contribs[i] for i in range(max_p) if not folded[i] and contribs[i] > 0))
    if not caps:
        caps = sorted(set(c for c in contribs if c > 0))

    payouts = [0] * max_p
    pot_rows = []
    prev = 0
    for ci, cap in enumerate(caps):
        slice_pot = sum(max(0, min(contribs[i], cap) - prev) for i in range(max_p))
        prev = cap
        if slice_pot <= 0:
            continue
        eligible = [i for i in range(max_p) if contribs[i] >= cap and not folded[i]]
        if not eligible:
            eligible = [i for i in range(max_p) if not folded[i]]
        if not eligible:
            continue
        best = min(scores[i] for i in eligible)
        winners = [i for i in eligible if scores[i] == best]
        split = slice_pot // len(winners)
        rem = slice_pot - split * len(winners)
        for w in winners:
            payouts[w] += split
        if rem:
            payouts[winners[0]] += rem  # 나머지 칩은 첫 승자에게
        pot_rows.append({
            "label": "메인 팟" if ci == 0 else f"사이드 팟 {ci}",
            "pot_amt": slice_pot,
            "cap_amt": cap,
            "eligible": eligible,
            "winners": winners,
            "split": split,
        })

    for i in range(max_p):
        room["seats"][i]["chips"] += payouts[i]

    revealed = [i for i in range(max_p) if not folded[i]]
    room["result"] = {
        "type": "showdown",
        "payouts": payouts,
        "contribs": contribs,
        "pot_rows": pot_rows,
        "revealed": revealed,
        "msg": "쇼다운 완료",
    }
    room["pot"] = 0
    room["stage"] = "IDLE"
    room["active_seat"] = -1
    _log(room, "🏆 쇼다운 완료")
    _bump(room)


# ==========================================
# 타임아웃 (방치된 사람 턴 자동 처리)
# ==========================================
def enforce_timeout(room):
    """사람 턴이 TURN_SECONDS 를 초과하면 자동으로 체크/폴드 처리.
    아무 클라이언트 렌더에서나 호출될 수 있다(락 보유 상태)."""
    if room["stage"] in ("LOBBY", "IDLE", "SHOWDOWN"):
        return False
    cur = room["active_seat"]
    if cur < 0:
        return False
    s = room["seats"][cur]
    if s["kind"] != "HUMAN":
        return False
    if time.time() < room["turn_deadline"]:
        return False
    need = room["current_max_bet"] - s["bet"]
    _log(room, f"⏱️ {s['name']} 시간 초과 → 자동 {'체크' if need <= 0 else '폴드'}")
    player_action(room, cur, "check" if need <= 0 else "fold")
    return True


def time_left(room):
    if room["stage"] in ("LOBBY", "IDLE", "SHOWDOWN") or room["active_seat"] < 0:
        return 0
    return max(0, int(room["turn_deadline"] - time.time()))


# ==========================================
# 리바이 (사람 전용 수동)
# ==========================================
def rebuy(room, idx):
    s = room["seats"][idx]
    if s["kind"] != "HUMAN" or s["chips"] > 0 or s["rebuys"] <= 0:
        return False
    s["chips"] = room["config"]["start_chips"]
    s["rebuys"] -= 1
    s["eliminated"] = False
    _log(room, f"🔄 {s['name']} 리바이 (남은 {s['rebuys']}회)")
    _bump(room)
    return True


def reset_tournament(room):
    """참가자는 유지한 채 칩/탈락 상태를 초기화하고 로비로 되돌린다."""
    cfg = room["config"]
    for s in room["seats"]:
        if s["kind"] != "EMPTY":
            s.update({
                "chips": cfg["start_chips"],
                "rebuys": cfg["rebuys"],
                "eliminated": False,
                "folded": True,
                "in_hand": False,
                "hole": [], "bet": 0, "contrib": 0, "last_action": "",
            })
    room.update({
        "stage": "LOBBY", "hand_no": 0, "pot": 0, "board": [],
        "result": None, "active_seat": -1, "winner_seat": None,
        "acted": [], "current_max_bet": 0, "deck": [],
    })
    room["log"] = []
    _log(room, "🔄 새 토너먼트를 시작합니다.")
    _bump(room)
