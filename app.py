import random
import streamlit as st
import plotly.graph_objects as go
from treys import Card, Deck, Evaluator

# ==========================================
# 0. 페이지 기본 설정 및 초기 세션 상태
# ==========================================
st.set_page_config(
    page_title="텍사스 홀덤 실시간 승률 & 수학적 어드바이저",
    page_icon="♠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

RANKS = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"]
SUITS = ["s", "h", "d", "c"]
SUIT_SYMBOLS = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}

EVALUATOR = Evaluator()

# 세션 상태 초기화
if "hero_card1" not in st.session_state:
    st.session_state.hero_card1 = "As"
if "hero_card2" not in st.session_state:
    st.session_state.hero_card2 = "Ks"
if "board_cards" not in st.session_state:
    st.session_state.board_cards = []
if "bet_ratio_pct" not in st.session_state:
    st.session_state.bet_ratio_pct = 50.0  # 기본 50% 팟 베팅


# ==========================================
# 1. 169 핸드 명시적 티어(S, A, B, C, D) 딕셔너리 정의
# ==========================================
TIER_S = {"AA", "KK", "QQ", "JJ", "TT", "AKs", "AQs", "AKo"}
TIER_A = {"99", "88", "AJs", "ATs", "KQs", "KJs", "QJs", "JTs", "AQo", "AJo", "KQo"}
TIER_B = {
    "77", "66", "55",
    "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
    "KTs", "K9s", "QTs", "Q9s", "J9s", "T9s", "98s", "87s",
    "ATo", "KJo", "KTo", "QJo", "QTo", "JTo"
}
TIER_C = {
    "44", "33", "22",
    "K8s", "K7s", "K6s", "K5s", "K4s", "K3s", "K2s",
    "Q8s", "Q7s", "Q6s", "Q5s", "Q4s", "Q3s", "Q2s",
    "J8s", "J7s", "J6s", "J5s",
    "T8s", "T7s", "T6s",
    "97s", "96s", "86s", "85s", "76s", "75s", "65s", "64s", "54s", "53s", "43s",
    "A9o", "A8o", "A7o", "A6o", "A5o", "A4o", "A3o", "A2o",
    "K9o", "K8o", "K7o", "Q9o", "Q8o", "J9o", "J8o", "T9o", "T8o", "98o", "87o", "76o", "65o"
}


# ==========================================
# 2. 사이드바: UI 테마 (라이트 모드 기본) 및 기본 옵션
# ==========================================
opponents_count = st.sidebar.slider("상대 플레이어 수", min_value=1, max_value=8, value=2)
sim_iterations = st.sidebar.select_slider("정밀도 (시뮬레이션)", options=[1000, 2500, 5000], value=2500)

st.sidebar.markdown("---")
st.sidebar.title("⚙️ 설정 & 게임 옵션")

theme_mode = st.sidebar.radio("🎨 UI 테마 선택", ["☀️ 라이트 모드", "🌙 다크 모드"], index=0)
is_dark = (theme_mode == "🌙 다크 모드")

# ==========================================
# 3. 테마별 고대비 색상 체계 및 커스텀 CSS
# ==========================================
if is_dark:
    app_bg = "#
