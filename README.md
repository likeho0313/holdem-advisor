# 홀덤 핸드·액션 어드바이저

WPL의 프리플랍 핸드레인지 차트에서 사용하는 169개 핸드 조합 개념을 참고한 Streamlit 앱입니다. WPL의 이미지나 로고를 복제하지 않고, 표 형태를 자체 구현했습니다.

## 주요 기능
- 초기 시드(내 스택) 설정
- 빅블라인드 입력 시 스몰블라인드 자동 계산(BB / 2)
- 앤티(ENT) 입력
- 1~10번 좌석, 내 자리, 상대 자리, 시작 플레이어 지정
- 169개 핸드 조합표와 실제 무늬 조합 선택
- 프리플랍 및 플랍/턴/리버 기준 승률 추정
- 팟 오즈 기반 콜/폴드/올인 참고 액션
- 블라인드·앤티만 초기화(초기 시드는 유지), 게임 전체 초기화

## 로컬 실행
Python 3.10 이상 권장.

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 접속합니다.

## 인터넷 공개 배포
1. GitHub에 새 저장소를 만듭니다.
2. `app.py`, `requirements.txt`, `README.md`를 저장소 루트에 올립니다.
3. Streamlit Community Cloud에 GitHub 계정으로 로그인합니다.
4. Create app에서 저장소, 브랜치(`main`), 엔트리 파일(`app.py`)을 선택하고 Deploy를 누릅니다.
5. 생성된 `*.streamlit.app` 주소로 외부에서 접속합니다.

## 계산상의 한계
상대의 비공개 핸드는 무작위라고 가정한 몬테카를로 추정치입니다. 상대 핸드 범위, 베팅 이력, 포지션별 전략, 토너먼트 ICM을 반영한 GTO 솔버가 아닙니다. 추천 액션은 참고용이며 결과를 보장하지 않습니다.
