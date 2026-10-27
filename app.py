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
# 2. 사이드바: 옵션 슬라이더 및 테마 선택 (요청된 지정 순서)
# ==========================================
opponents_count = st.sidebar.slider("상대 플레이어 수", min_value=1, max_value=8, value=2)
sim_iterations = st.sidebar.select_slider("정밀도 (시뮬레이션)", options=[1000, 2500, 5000], value=2500)

st.sidebar.markdown("---")

st.sidebar.title("⚙️ 설정 & 게임 옵션")

theme_mode = st.sidebar.radio("🎨 UI 테마 선택", ["☀️ 라이트 모드", "🌙 다크 모드"], index=0)
is_dark = (theme_mode == "🌙 다크 모드")


# ==========================================
# 3. 테마별 고대비 색상 체계 설정
# ==========================================
if is_dark:
    app_bg = "#0f172a"
    card_bg = "#1e293b"
    text_main = "#f8fafc"
    text_sub = "#94a3b8"
    border_col = "#334155"
    
    bg_s = "#14532d"  # S급: 다크 에메랄드
    bg_a = "#1e3a8a"  # A급: 다크 네이비
    bg_b = "#713f12"  # B급: 다크 브론즈
    bg_c = "#581c87"  # C급: 다크 퍼플 (#581c87)
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
    bg_c = "#e9d5ff"  # C급: 파스텔 퍼플 (#e9d5ff)
    bg_d = "#ffffff"  # D급: 순백색
    
    badge_txt = "#0f172a"
    txt_pair = "#1d4ed8"
    txt_suited = "#15803d"
    txt_off = "#c2410c"
    
    btn_preset_active_bg = "#2563eb"
    btn_preset_active_txt = "#ffffff"
    btn_preset_inactive_bg = "#ffffff"
    btn_preset_inactive_txt = "#0f172a"


def hand_type(r1, r2):
    i1, i2 = RANKS.index(r1), RANKS.index(r2)
    if i1 == i2:
        return r1 + r2
    elif i1 < i2:
        return r1 + r2 + "s"
    else:
        return r2 + r1 + "o"


def get_hand_colors(r1, r2):
    ht = hand_type(r1, r2)
    i1, i2 = RANKS.index(r1), RANKS.index(r2)
    txt_color = txt_pair if i1 == i2 else (txt_suited if i1 < i2 else txt_off)
    
    if ht in TIER_S:
        return txt_color, bg_s
    elif ht in TIER_A:
        return txt_color, bg_a
    elif ht in TIER_B:
        return txt_color, bg_b
    elif ht in TIER_C:
        return txt_color, bg_c
    else:
        return txt_color, bg_d


def get_suit_md(suit_code):
    if suit_code in ["h", "d"]:
        return f":red[{SUIT_SYMBOLS[suit_code]}]"
    return SUIT_SYMBOLS[suit_code]


def format_card_md(rank, suit_code):
    rank_str = rank.replace("T", "10")
    symbol = SUIT_SYMBOLS[suit_code]
    if suit_code in ["h", "d"]:
        return f":red[{rank_str}{symbol}]"
    return f"{rank_str}{symbol}"


dynamic_button_styles = []

# 1) 169 핸드 표 버튼 스타일링
for r1 in RANKS:
    for r2 in RANKS:
        ht = hand_type(r1, r2)
        txt_col, bg_col = get_hand_colors(r1, r2)
        
        h1, h2 = st.session_state.hero_card1, st.session_state.hero_card2
        selected_ht = hand_type(h1[0], h2[0])
        is_selected = (ht == selected_ht)
        
        key_id = f"mat_{r1}_{r2}"
        
        if is_selected:
            btn_bg = "#dc2626"
            btn_txt = "#ffffff"
            btn_border = "#f59e0b"
            extra_style = "font-weight: 900 !important; box-shadow: 0 0 8px #f59e0b !important;"
        else:
            btn_bg = bg_col
            btn_txt = txt_col
            btn_border = border_col
            extra_style = ""
            
        dynamic_button_styles.append(f"""
            div[class*="st-key-{key_id}"] button,
            div[class*="st-key-{key_id}"] button:hover {{
                background-color: {btn_bg} !important;
                border: 1px solid {btn_border} !important;
                {extra_style}
            }}
            div[class*="st-key-{key_id}"] button * {{
                color: {btn_txt} !important;
                font-weight: bold !important;
            }}
        """)

# 2) 원클릭 카드 피커 버튼 스타일링
for r in RANKS:
    for s in SUITS:
        card_code = f"{r}{s}"
        key_id = f"pick_card_{card_code}"
        has_red = s in ["h", "d"]

        # 카드 피커 전용 변수명 사용: C급 배경색 bg_c와 충돌 방지
        picker_bg = (
            "#2a1215" if (is_dark and has_red)
            else "#1e293b" if is_dark
            else "#fef2f2" if has_red
            else "#ffffff"
        )

        border_c = (
            "#991b1b" if has_red
            else "#475569" if is_dark
            else "#cbd5e1"
        )

        dynamic_button_styles.append(f"""
            div[class*="st-key-{key_id}"] button,
            div[class*="st-key-{key_id}"] button:hover {{
                background-color: {picker_bg} !important;
                border: 1px solid {border_c} !important;
            }}
            div[class*="st-key-{key_id}"] button * {{
                font-weight: bold !important;
                font-size: 0.88rem !important;
            }}
        """)
# 3) 무늬 원클릭 변경 버튼 스타일링
all_combos = [("s", "h"), ("s", "d"), ("s", "c"), ("h", "d"), ("h", "c"), ("d", "c")]
for p1, p2 in all_combos:
    for prefix in ["quick_pair", "quick_off"]:
        key_id = f"{prefix}_{p1}_{p2}"
        bg_c = "#1e293b" if is_dark else "#ffffff"
        border_c = "#475569" if is_dark else "#cbd5e1"
        
        dynamic_button_styles.append(f"""
            div[class*="st-key-{key_id}"] button,
            div[class*="st-key-{key_id}"] button:hover {{
                background-color: {bg_c} !important;
                border: 1px solid {border_c} !important;
            }}
            div[class*="st-key-{key_id}"] button * {{
                font-weight: bold !important;
            }}
        """)

for s in SUITS:
    key_id = f"quick_suited_{s}"
    has_red = s in ["h", "d"]
    bg_c = "#2a1215" if (is_dark and has_red) else ("#1e293b" if is_dark else ("#fef2f2" if has_red else "#ffffff"))
    border_c = "#991b1b" if has_red else ("#475569" if is_dark else "#cbd5e1")
    
    dynamic_button_styles.append(f"""
        div[class*="st-key-{key_id}"] button,
        div[class*="st-key-{key_id}"] button:hover {{
            background-color: {bg_c} !important;
            border: 1px solid {border_c} !important;
        }}
        div[class*="st-key-{key_id}"] button * {{
            font-weight: bold !important;
        }}
    """)

# 4) % 팟 프리셋 버튼 스타일링
presets_vals = [25.0, 33.3, 50.0, 66.6, 75.0, 100.0, 150.0, 200.0]
for idx, val in enumerate(presets_vals):
    key_id = f"preset_btn_{idx}"
    is_active = (st.session_state.bet_ratio_pct == val)
    
    p_bg = btn_preset_active_bg if is_active else btn_preset_inactive_bg
    p_txt = btn_preset_active_txt if is_active else btn_preset_inactive_txt
    p_border = "#1d4ed8" if (is_active and not is_dark) else ("#60a5fa" if is_active else border_col)
    
    dynamic_button_styles.append(f"""
        div[class*="st-key-{key_id}"] button,
        div[class*="st-key-{key_id}"] button:hover,
        div[class*="st-key-{key_id}"] button:focus {{
            background-color: {p_bg} !important;
            border: 1px solid {p_border} !important;
        }}
        div[class*="st-key-{key_id}"] button * {{
            color: {p_txt} !important;
            font-weight: bold !important;
        }}
    """)

# 전역 CSS 주입 (범례 뱃지 CSS 전용 클래스 정의)
st.markdown(f"""
    <style>
    .stApp {{
        background-color: {app_bg} !important;
        color: {text_main} !important;
    }}
    
    div[data-testid="stHorizontal"] > div {{
        padding: 0px 1px !important;
    }}
    
    .stButton button {{
        width: 100% !important;
        padding: 3px 0px !important;
        font-size: 0.80rem !important;
        min-height: 36px !important;
        border-radius: 4px !important;
    }}
    
    {" ".join(dynamic_button_styles)}

    /* ★ 범례 전용 CSS 클래스 정의 (100% 배경색 출력) ★ */
    .legend-badge {{
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.85rem;
    }}
    .badge-s {{ background-color: {bg_s} !important; color: {badge_txt} !important; }}
    .badge-a {{ background-color: {bg_a} !important; color: {badge_txt} !important; }}
    .badge-b {{ background-color: {bg_b} !important; color: {badge_txt} !important; }}
    .badge-c {{ background-color: {bg_c} !important; color: {badge_txt} !important; }}
    .badge-d {{ background-color: {bg_d} !important; color: {badge_txt} !important; border: 1px solid #cbd5e1; }}

    .card-badge {{
        display: inline-block;
        padding: 4px 10px;
        font-size: 1.1rem;
        font-weight: bold;
        border-radius: 6px;
        margin: 2px;
    }}
    .suit-s, .suit-c {{ background-color: #1e293b; color: #ffffff; border: 1px solid #475569; }}
    .suit-h, .suit-d {{ background-color: #450a0a; color: #f87171; border: 1px solid #991b1b; }}
    
    .action-card {{
        background-color: {card_bg};
        border-radius: 8px;
        padding: 15px;
        border: 1px solid {border_col};
        text-align: center;
        margin-top: 10px;
    }}
    .action-title {{ font-size: 1.5rem; font-weight: bold; }}
    .action-fold {{ color: #f87171; }}
    .action-check {{ color: #38bdf8; }}
    .action-call {{ color: #facc15; }}
    .action-raise {{ color: #4ade80; }}
    .action-allin {{ color: #fb923c; }}

    @media screen and (max-height: 650px), (max-width: 920px) {{
        .block-container {{ padding: 0.5rem !important; }}
        .stButton button {{
            padding: 1px 0px !important;
            font-size: 0.72rem !important;
            min-height: 28px !important;
        }}
        .card-badge {{ padding: 2px 5px !important; font-size: 0.9rem !important; }}
    }}
    </style>
""", unsafe_allow_html=True)


# ==========================================
# 4. 헬퍼 계산 함수
# ==========================================
def format_card_html(card_code):
    if not card_code or len(card_code) < 2:
        return ""
    rank = card_code[0].replace("T", "10")
    suit = card_code[1]
    symbol = SUIT_SYMBOLS.get(suit, "")
    css_class = f"suit-{suit}"
    return f'<span class="card-badge {css_class}">{rank}{symbol}</span>'


def calculate_monte_carlo_equity(hero_cards, board_cards, opponents_count, iterations=3000):
    known_cards = hero_cards + board_cards
    full_deck = Deck.GetFullDeck()
    deck = [c for c in full_deck if c not in known_cards]
    
    missing_board_count = 5 - len(board_cards)
    draw_count = missing_board_count + (opponents_count * 2)
    
    wins, ties, losses = 0.0, 0.0, 0.0
    
    for _ in range(iterations):
        drawn = random.sample(deck, draw_count)
        sim_board = board_cards + drawn[:missing_board_count]
        
        offset = missing_board_count
        opponents_cards = []
        for _ in range(opponents_count):
            opponents_cards.append(drawn[offset:offset+2])
            offset += 2
            
        hero_score = EVALUATOR.evaluate(sim_board, hero_cards)
        opp_scores = [EVALUATOR.evaluate(sim_board, opp) for opp in opponents_cards]
        
        best_opp_score = min(opp_scores)
        
        if hero_score < best_opp_score:
            wins += 1.0
        elif hero_score == best_opp_score:
            tying_count = opp_scores.count(hero_score) + 1
            ties += (1.0 / tying_count)
        else:
            losses += 1.0
            
    equity = (wins + ties) / iterations
    return equity, wins/iterations, ties/iterations, (iterations - wins - ties)/iterations


def calculate_pot_odds_math(bet_pct):
    b = bet_pct / 100.0
    equity_to_call = (b / (1.0 + 2.0 * b)) * 100.0
    ratio_first = round((1.0 + b) / b, 1) if b > 0 else 0
    
    outs_flop = round(equity_to_call / 4.0, 1)
    outs_turn = round(equity_to_call / 2.0, 1)
    
    return equity_to_call, f"{ratio_first} : 1", outs_flop, outs_turn


# ==========================================
# 5. 메인 화면: 169 핸드 매트릭스
# ==========================================
st.title("♠️ 실시간 홀덤 승률 & 수학적 어드바이저")

# ★ 배경 색상 범례 (CSS 클래스 연동 방식) ★
st.markdown(f"""
    <div style="font-size:0.85rem; margin-bottom:8px; color:{text_sub}; font-weight:bold;">
        <b>글씨 색상:</b> 
        <span style="color:{txt_pair};">파랑(페어)</span> | 
        <span style="color:{txt_suited};">초록(수딧)</span> | 
        <span style="color:{txt_off};">주황(오프수딧)</span> &nbsp;&nbsp;|&nbsp;&nbsp; 
        <b>배경 색상:</b> 
        <span class="legend-badge badge-s">S급</span> 
        <span class="legend-badge badge-a">A급</span> 
        <span class="legend-badge badge-b">B급</span> 
        <span class="legend-badge badge-c">C급</span> 
        <span class="legend-badge badge-d">D급</span>
    </div>
""", unsafe_allow_html=True)

# 13x13 매트릭스 그리드
matrix_cols = st.columns([0.6] + [1]*13)
matrix_cols[0].write("")
for j, r in enumerate(RANKS):
    matrix_cols[j+1].markdown(f"**{r}**")
    
for i, r1 in enumerate(RANKS):
    m_row = st.columns([0.6] + [1]*13)
    m_row[0].markdown(f"**{r1}**")
    for j, r2 in enumerate(RANKS):
        ht = hand_type(r1, r2)
        if m_row[j+1].button(ht, key=f"mat_{r1}_{r2}", use_container_width=True):
            if r1 == r2:
                st.session_state.hero_card1 = f"{r1}s"
                st.session_state.hero_card2 = f"{r2}h"
            elif RANKS.index(r1) < RANKS.index(r2):
                st.session_state.hero_card1 = f"{r1}s"
                st.session_state.hero_card2 = f"{r2}s"
            else:
                st.session_state.hero_card1 = f"{r1}s"
                st.session_state.hero_card2 = f"{r2}h"
            st.rerun()


# ==========================================
# 6. 선택 핸드 및 원클릭 무늬 프리셋
# ==========================================
st.markdown("---")
h1, h2 = st.session_state.hero_card1, st.session_state.hero_card2
r1, r2 = h1[0], h2[0]
s1, s2 = h1[1], h2[1]
ht = hand_type(r1, r2)

hero_cards = [h1, h2]
h_html = "".join([format_card_html(c) for c in hero_cards])

st.markdown(f"### 📌 내 핸드: {h_html} `({ht})`", unsafe_allow_html=True)

st.write("⚡ **무늬(Suit) 원클릭 변경:**")

if r1 == r2:  # Pair
    pair_combos = [("s", "h"), ("s", "d"), ("s", "c"), ("h", "d"), ("h", "c"), ("d", "c")]
    p_cols = st.columns(6)
    for idx, (p1, p2) in enumerate(pair_combos):
        sm1, sm2 = get_suit_md(p1), get_suit_md(p2)
        c1_md, c2_md = format_card_md(r1, p1), format_card_md(r2, p2)
        btn_label = f"{sm1}{sm2} ({c1_md} {c2_md})"
        if p_cols[idx].button(btn_label, key=f"quick_pair_{p1}_{p2}", use_container_width=True):
            st.session_state.hero_card1 = f"{r1}{p1}"
            st.session_state.hero_card2 = f"{r2}{p2}"
            st.rerun()

elif s1 == s2:  # Suited
    s_cols = st.columns(4)
    for idx, suit in enumerate(SUITS):
        sm = get_suit_md(suit)
        c1_md, c2_md = format_card_md(r1, suit), format_card_md(r2, suit)
        btn_label = f"{sm}{sm} ({c1_md} {c2_md})"
        if s_cols[idx].button(btn_label, key=f"quick_suited_{suit}", use_container_width=True):
            st.session_state.hero_card1 = f"{r1}{suit}"
            st.session_state.hero_card2 = f"{r2}{suit}"
            st.rerun()

else:  # Offsuit
    off_combos = [("s", "h"), ("s", "d"), ("s", "c"), ("h", "d"), ("h", "c"), ("d", "c")]
    o_cols = st.columns(6)
    for idx, (p1, p2) in enumerate(off_combos):
        sm1, sm2 = get_suit_md(p1), get_suit_md(p2)
        c1_md, c2_md = format_card_md(r1, p1), format_card_md(r2, p2)
        btn_label = f"{sm1}{sm2} ({c1_md} {c2_md})"
        if o_cols[idx].button(btn_label, key=f"quick_off_{p1}_{p2}", use_container_width=True):
            st.session_state.hero_card1 = f"{r1}{p1}"
            st.session_state.hero_card2 = f"{r2}{p2}"
            st.rerun()


# ==========================================
# 7. 원클릭 보드 선택
# ==========================================
st.markdown("---")
st.subheader("🃏 커뮤니티 보드 카드 선택 (플랍 · 턴 · 리버)")

used_cards = set(hero_cards + st.session_state.board_cards)

slot_names = ["플랍 1", "플랍 2", "플랍 3", "턴 (Turn)", "리버 (River)"]
slot_cols = st.columns(5)

for i in range(5):
    with slot_cols[i]:
        st.caption(f"**{slot_names[i]}**")
        if i < len(st.session_state.board_cards):
            card_code = st.session_state.board_cards[i]
            st.markdown(format_card_html(card_code), unsafe_allow_html=True)
            if st.button("❌ 삭제", key=f"remove_board_{i}", use_container_width=True):
                st.session_state.board_cards.pop(i)
                st.rerun()
        else:
            st.markdown("<div style='color:gray; padding:6px; font-size:0.85rem;'>[ 빈 슬롯 ]</div>", unsafe_allow_html=True)

if st.session_state.board_cards:
    if st.button("🗑️ 보드 카드 전체 초기화", type="secondary"):
        st.session_state.board_cards = []
        st.rerun()

st.markdown("<br>", unsafe_allow_html=True)
st.write("👉 **원클릭 카드 피커 (선택된 카드는 자동 숨김):**")

for s in SUITS:
    suit_row = st.columns([0.8] + [1]*13)
    suit_row[0].markdown(f"### {get_suit_md(s)}")
    for j, r in enumerate(RANKS):
        card_code = f"{r}{s}"
        btn_label = format_card_md(r, s)
        
        is_used = card_code in used_cards
        is_full = len(st.session_state.board_cards) >= 5
        
        if is_used:
            suit_row[j+1].markdown("<div style='min-height:36px;'></div>", unsafe_allow_html=True)
        else:
            if suit_row[j+1].button(
                btn_label,
                key=f"pick_card_{card_code}",
                disabled=is_full,
                use_container_width=True
            ):
                if len(st.session_state.board_cards) < 5:
                    st.session_state.board_cards.append(card_code)
                    st.rerun()

board_cards = st.session_state.board_cards
b_html = "".join([format_card_html(c) for c in board_cards]) if board_cards else "<span style='color:gray;'>프리플랍 (보드 없음)</span>"
st.markdown(f"**현재 확정 보드:** {b_html}", unsafe_allow_html=True)


# ==========================================
# 8. 팟 오즈 & 아웃츠 참조 수학 계산기
# ==========================================
st.markdown("---")
st.subheader("📊 상대 베팅 크기 & 팟 오즈(Pot Odds) 원클릭 선택")
st.caption("팟 사이즈를 계산할 시간이 없을 때 상대방이 베팅한 상대적 크기를 선택하세요.")

preset_cols = st.columns(8)
presets = [
    ("25% 팟", 25.0),
    ("33% 팟", 33.3),
    ("50% 팟", 50.0),
    ("66% 팟", 66.6),
    ("75% 팟", 75.0),
    ("100% (팟)", 100.0),
    ("150% (오버)", 150.0),
    ("200% (2배)", 200.0),
]

for idx, (label, val) in enumerate(presets):
    if preset_cols[idx].button(
        label,
        key=f"preset_btn_{idx}",
        use_container_width=True
    ):
        st.session_state.bet_ratio_pct = val
        st.rerun()

req_eq, pot_ratio_str, outs_req_flop, outs_turn = calculate_pot_odds_math(st.session_state.bet_ratio_pct)

m_cols = st.columns(4)
m_items = [
    ("선택한 베팅 크기", f"팟의 {st.session_state.bet_ratio_pct:.0f}%"),
    ("팟 오즈 비율 (Pot Odds)", pot_ratio_str),
    ("콜에 필요한 최소 승률", f"{req_eq:.1f}%"),
    ("필요 아웃츠 (Flop/Turn)", f"약 {outs_req_flop:.0f}개 / {outs_turn:.0f}개")
]

for idx, (title, val_str) in enumerate(m_items):
    m_cols[idx].markdown(f"""
        <div style="background-color:{card_bg}; border:1px solid {border_col}; border-radius:8px; padding:12px; text-align:center;">
            <div style="color:{text_sub}; font-size:0.85rem; font-weight:bold;">{title}</div>
            <div style="color:{text_main}; font-size:1.35rem; font-weight:bold; margin-top:4px;">{val_str}</div>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

with st.expander("📖 베팅 크기별 필요 승률 & 아웃츠(Outs) 가이드 참조표", expanded=False):
    st.markdown("""
    | Bet Size (% of Pot) | 필요 승률 (Equity to Call) | 필요 아웃츠 (Flop 기준) | 필요 아웃츠 (Turn 기준) |
    | :---: | :---: | :---: | :---: |
    | **25%** | **16%** | **4개** | **8개** |
    | **33%** | **20%** | **5개** | **10개** |
    | **50%** | **25%** | **6~7개** | **12~13개** |
    | **66%** | **28%** | **7개** | **14개** |
    | **75%** | **30%** | **7~8개** | **15개** |
    | **100%** | **33%** | **8~9개** | **16~17개** |
    | **150%** | **38%** | **9~10개** | **19개** |
    | **200%** | **40%** | **10개** | **20개** |
    """)


# ==========================================
# 9. 실시간 승률 및 수학적 진단 제안
# ==========================================
st.markdown("---")

invalid_board_count = len(board_cards) not in (0, 3, 4, 5)

if invalid_board_count:
    st.warning("⚠️ 보드 카드는 **0장(프리플랍)**, **3장(플랍)**, **4장(턴)**, **5장(리버)** 조합일 때 정확히 계산됩니다.")
else:
    if st.button("🚀 실시간 승률 계산 및 수학적 진단 확인", type="primary", use_container_width=True):
        try:
            with st.spinner("몬테카를로 승률 계산 및 수학적 가치 진단 중..."):
                hero_treys = [Card.new(c) for c in hero_cards]
                board_treys = [Card.new(c) for c in board_cards]
                
                equity, win_rate, tie_rate, loss_rate = calculate_monte_carlo_equity(
                    hero_treys, board_treys, opponents_count, sim_iterations
                )

            eq_pct = equity * 100.0
            ev_diff = eq_pct - req_eq
            
            if eq_pct >= req_eq + 15.0:
                rec_action = "레이즈 / 올인 (Raise or All-in)"
                action_class = "action-allin"
                math_status = f"🔥 **압도적 +EV 상태 (승률 {eq_pct:.1f}% vs 필요 승률 {req_eq:.1f}%)**"
                advice_text = f"내 승률이 콜 필요 승률보다 **+{ev_diff:.1f}%p** 높습니다. 단순히 콜만 하는 것은 손해이며, 레이즈로 팟 크기를 대폭 키워야 하는 수학적 최고 가치 구간입니다."
            elif eq_pct >= req_eq:
                rec_action = "콜 추천 (Call)"
                action_class = "action-call"
                math_status = f"✅ **양의 기대값(+EV) 콜 구간 (승률 {eq_pct:.1f}% vs 필요 승률 {req_eq:.1f}%)**"
                advice_text = f"내 승률이 팟 오즈가 요구하는 최소 승률을 **+{ev_diff:.1f}%p** 웃돌고 있습니다. 수학적으로 장기 반복 시 무조건 칩을 버는 구간이므로 **콜(Call)**이 적절합니다."
            elif eq_pct >= req_eq - 5.0:
                rec_action = "콜 또는 폴드 (Marginal Call / Fold)"
                action_class = "action-check"
                math_status = f"⚠️ **경계선 구간 (승률 {eq_pct:.1f}% vs 필요 승률 {req_eq:.1f}%)**"
                advice_text = f"승률이 필요 승률에 비해서 **{abs(ev_diff):.1f}%p** 부족합니다. 상대의 베팅 성향이 블러핑이 많거나 후속 턴/리버에서 크게 먹을 수 있는 포지션이라면 콜을 고려할 수 있습니다."
            else:
                rec_action = "폴드 권장 (Fold)"
                action_class = "action-fold"
                math_status = f"🛑 **음의 기대값(-EV) 손실 구간 (승률 {eq_pct:.1f}% vs 필요 승률 {req_eq:.1f}%)**"
                advice_text = f"현재 승률({eq_pct:.1f}%)로는 팟 오즈 필요 승률({req_eq:.1f}%)을 충족하지 못합니다 (**{ev_diff:.1f}%p 부족**). 이 상황에서 콜을 반복하면 지속적으로 칩이 감소하므로 **폴드(Fold)**가 수학적 정석입니다."

            res1, res2, res3, res4 = st.columns(4)
            res1.metric("내 최종 승률 (Equity)", f"{eq_pct:.1f}%")
            res2.metric("콜 필요 승률 (Equity to Call)", f"{req_eq:.1f}%")
            res3.metric("기대값 차이 (EV Diff)", f"{ev_diff:+.1f}%p", delta=f"{ev_diff:+.1f}%p")
            res4.metric("추정 필요 아웃츠", f"약 {outs_req_flop:.0f}개")

            st.markdown(f"""
                <div class="action-card">
                    <div style="color: {text_sub}; font-size: 0.95rem;">수학적 판정 결과</div>
                    <div class="action-title {action_class}">{rec_action}</div>
                    <div style="margin-top: 8px; font-size: 1.05rem;">{math_status}</div>
                </div>
            """, unsafe_allow_html=True)

            st.info(f"💡 **수학적 가치 진단 상세:**\n\n{advice_text}")

            fig = go.Figure(data=[go.Pie(
                labels=['승리', '비김', '패배'],
                values=[win_rate*100, tie_rate*100, loss_rate*100],
                hole=.4,
                marker_colors=['#4ade80', '#facc15', '#f87171']
            )])
            fig.update_layout(
                template="plotly_dark" if is_dark else "plotly_white",
                height=250,
                margin=dict(l=10, r=10, t=20, b=20),
                showlegend=True
            )
            st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error(f"계산 도중 오류가 발생했습니다: {str(e)}")
