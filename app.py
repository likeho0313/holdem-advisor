import random
import streamlit as st
import plotly.graph_objects as go
from treys import Card, Deck, Evaluator

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

if "hero_card1" not in st.session_state:
    st.session_state.hero_card1 = "As"
if "hero_card2" not in st.session_state:
    st.session_state.hero_card2 = "Ks"
if "board_cards" not in st.session_state:
    st.session_state.board_cards = []
if "bet_ratio_pct" not in st.session_state:
    st.session_state.bet_ratio_pct = 50.0

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
    "T8s", "T7s", "T6s", "97s", "96s", "86s", "85s", "76s", "75s", "65s", "64s", "54s", "53s", "43s",
    "A9o", "A8o", "A7o", "A6o", "A5o", "A4o", "A3o", "A2o",
    "K9o", "K8o", "K7o", "Q9o", "Q8o", "J9o", "J8o", "T9o", "T8o", "98o", "87o", "76o", "65o"
}

# 사이드바 순서
opponents_count = st.sidebar.slider("상대 플레이어 수", min_value=1, max_value=8, value=2)
sim_iterations = st.sidebar.select_slider("정밀도 (시뮬레이션)", options=[1000, 2500, 5000], value=2500)

st.sidebar.markdown("---")

st.sidebar.title("⚙️ 설정 & 게임 옵션")

theme_mode = st.sidebar.radio("🎨 UI 테마 선택", ["☀️ 라이트 모드", "🌙 다크 모드"], index=0)
is_dark = (theme_mode == "🌙 다크 모드")

if is_dark:
    app_bg = "#0f172a"
    card_bg = "#1e293b"
    text_main = "#f8fafc"
    text_sub = "#94a3b8"
    border_col = "#334155"
    
    bg_s = "#14532d"  # S급: 다크 에메랄드
    bg_a = "#1e3a8a"  # A급: 다크 네이비
    bg_b = "#713f12"  # B급: 다크 브론즈
    bg_c = "#581c87"  # C급: 다크 퍼플
    bg_d = "#1e293b"  # D급: 다크 슬레이트
    
    badge_txt = "#ffffff"
    txt_pair = "#93c5fd"
    txt_suited = "#86efac"
    txt_off = "#fdba74"
    
    btn_preset_active_bg = "#3b82f6"
    btn_preset_active_txt = "#ffffff"
    btn_preset_inactive_bg = "#1e293b"
    btn_preset_inactive_txt = "#f8fafc"
else:
    app_bg = "#f8fafc"
    card_bg = "#ffffff"
    text_main = "#0f172a"
    text_sub = "#475569"
    border_col = "#cbd5e1"
    
    bg_s = "#a7f3d0"  # S급: 파스텔 민트
    bg_a = "#bae6fd"  # A급: 파스텔 블루
    bg_b = "#fef08a"  # B급: 파스텔 옐로우
    bg_c = "#e9d5ff"  # C급: 파스텔 퍼플
    bg_d = "#ffffff"  # D급: 순백색
    
    badge_txt = "#0f172a"
    txt_pair = "#1d4ed8"
    txt_suited = "#15803d"
    txt_off = "#c2410c"
    
    btn_preset_active_bg = "#2563eb"
    btn_preset_active_txt = "#ffffff"
    btn_preset_inactive_bg = "#ffffff"
    btn_preset_inactive_txt = "#0f172a"

# 독립된 HTML 변수 분리 (범례 배경 색상 100% 보장)
badge_s_html = f'<span style="background-color: {bg_s}; color: {badge_txt}; padding: 3px 8px; border-radius: 4px; font-weight: bold; display: inline-block;">S급</span>'
badge_a_html = f'<span style="background-color: {bg_a}; color: {badge_txt}; padding: 3px 8px; border-radius: 4px; font-weight: bold; display: inline-block;">A급</span>'
badge_b_html = f'<span style="background-color: {bg_b}; color: {badge_txt}; padding: 3px 8px; border-radius: 4px; font-weight: bold; display: inline-block;">B급</span>'
badge_c_html = f'<span style="background-color: {bg_c}; color: {badge_txt}; padding: 3px 8px; border-radius: 4px; font-weight: bold; display: inline-block;">C급</span>'
badge_d_html = f'<span style="background-color: {bg_d}; color: {badge_txt}; padding: 3px 8px; border-radius: 4px; font-weight: bold; border: 1px solid {border_col}; display: inline-block;">D급</span>'

h1, h2 = st.session_state.hero_card1, st.session_state.hero_card2
cur_s1, cur_s2 = h1[1], h2[1]

dynamic_button_styles = []

# 무늬 변경 하이라이트 버튼
all_combos = [("s", "h"), ("s", "d"), ("s", "c"), ("h", "d"), ("h", "c"), ("d", "c")]
for p1, p2 in all_combos:
    for prefix in ["quick_pair", "quick_off"]:
        key_id = f"{prefix}_{p1}_{p2}"
        is_selected = (cur_s1 == p1 and cur_s2 == p2) or (cur_s1 == p2 and cur_s2 == p1)
        
        if is_selected:
            bg_c_btn = "#dc2626" if is_dark else "#ef4444"
            border_c_btn = "#f59e0b"
            extra_s = "font-weight: 900 !important; box-shadow: 0 0 8px #f59e0b !important;"
        else:
            bg_c_btn = "#1e293b" if is_dark else "#ffffff"
            border_c_btn = "#475569" if is_dark else "#cbd5e1"
            extra_s = ""
        
        dynamic_button_styles.append(f"""
            div[class*="st-key-{key_id}"] button,
            div[class*="st-key-{key_id}"] button:hover {{
                background-color: {bg_c_btn} !important;
                border: 2px solid {border_c_btn} !important;
                {extra_s}
            }}
            div[class*="st-key-{key_id}"] button * {{
                font-weight: bold !important;
            }}
        """)

print("Python execution test PASSED!")
