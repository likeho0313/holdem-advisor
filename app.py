import random
import streamlit as st
import plotly.graph_objects as go
from treys import Card, Deck, Evaluator

# ==========================================
# 0. 페이지 기본 설정 및 초기 세션 상태
# ==========================================
st.set_page_config(
    page_title="텍사스 홀덤 실시간 승률 & 액션 어드바이저",
    page_icon="♠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

RANKS = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"]
SUITS = ["s", "h", "d", "c"]
SUIT_SYMBOLS = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
SUIT_NAMES = {"s": "스페이드(♠)", "h": "하트(♥)", "d": "다이아(♦)", "c": "클로버(♣)"}

EVALUATOR = Evaluator()

# 세션 상태 초기화
if "hero_card1" not in st.session_state:
    st.session_state.hero_card1 = "As"
if "hero_card2" not in st.session_state:
    st.session_state.hero_card2 = "Ks"
if "board_cards" not in st.session_state:
    st.session_state.board_cards = []


# ==========================================
# 1. 사이드바: UI 테마 (라이트 모드 디폴트) 및 게임 옵션
# ==========================================
st.sidebar.title("⚙️ 설정 & 게임 옵션")

# 라이트 모드를 디폴트(index=0)로 지정
theme_mode = st.sidebar.radio("🎨 UI 테마 선택", ["☀️ 라이트 모드", "🌙 다크 모드"], index=0)
is_dark = (theme_mode == "🌙 다크 모드")

st.sidebar.markdown("---")
opponents_count = st.sidebar.slider("상대 플레이어 수", min_value=1, max_value=8, value=2)
pot_size = st.sidebar.number_input("현재 팟 금액 ($)", min_value=0.0, value=100.0, step=10.0)
call_amount = st.sidebar.number_input("콜 필요 금액 ($)", min_value=0.0, value=20.0, step=5.0)
sim_iterations = st.sidebar.select_slider("정밀도 (시뮬레이션)", options=[1000, 2500, 5000], value=2500)


# ==========================================
# 2. 테마별 고대비 색상 체계 및 커스텀 CSS 생성
# ==========================================
if is_dark:
    app_bg = "#0f172a"
    card_bg = "#1e293b"
    text_main = "#f8fafc"
    text_sub = "#94a3b8"
    border_col = "#334155"
    
    # 169 표 배경색 (다크 모드)
    bg_s = "#14532d"  # S급
    bg_a = "#1e3a8a"  # A급
    bg_b = "#713f12"  # B급
    bg_c = "#334155"  # C급
    bg_d = "#1e293b"  # D급
    
    # 표 글자색 (다크 모드)
    txt_pair = "#93c5fd"    # 페어: 밝은 파랑
    txt_suited = "#86efac"  # 수딧: 밝은 초록
    txt_off = "#fdba74"     # 오프수딧: 밝은 주황
else:
    app_bg = "#f8fafc"
    card_bg = "#ffffff"
    text_main = "#0f172a"
    text_sub = "#475569"
    border_col = "#cbd5e1"
    
    # 169 표 배경색 (라이트 모드)
    bg_s = "#bbf7d0"  # S급
    bg_a = "#bfdbfe"  # A급
    bg_b = "#fef08a"  # B급
    bg_c = "#e2e8f0"  # C급
    bg_d = "#ffffff"  # D급
    
    # 표 글자색 (라이트 모드)
    txt_pair = "#1d4ed8"    # 페어: 진한 파랑
    txt_suited = "#15803d"  # 수딧: 진한 초록
    txt_off = "#c2410c"     # 오프수딧: 진한 주황


def hand_type(r1, r2):
    i1, i2 = RANKS.index(r1), RANKS.index(r2)
    if i1 == i2:
        return r1 + r2
    elif i1 < i2:
        return r1 + r2 + "s"
    else:
        return r2 + r1 + "o"


def get_hand_colors(r1, r2):
    i1, i2 = RANKS.index(r1), RANKS.index(r2)
    txt_color = txt_pair if i1 == i2 else (txt_suited if i1 < i2 else txt_off)
    
    v1, v2 = 12 - i1, 12 - i2
    if i1 > i2:
        v1, v2 = v2, v1
        
    if i1 == i2:
        bg_color = bg_s if v1 >= 9 else (bg_a if v1 >= 6 else (bg_b if v1 >= 3 else bg_c))
    elif i1 < i2:
        if (v1 >= 11 and v2 >= 10) or (v1 == 12 and v2 >= 8):
            bg_color = bg_s
        elif (v1 >= 10 and v2 >= 8) or (v1 == 12 and v2 >= 4) or (v1 >= 8 and v2 >= 7 and v1 - v2 == 1):
            bg_color = bg_a
        elif (v1 >= 8 and v2 >= 5) or (v1 - v2 <= 2 and v2 >= 4):
            bg_color = bg_b
        elif v1 >= 7:
            bg_color = bg_c
        else:
            bg_color = bg_d
    else:
        if (v1 == 12 and v2 >= 10) or (v1 == 11 and v2 == 10):
            bg_color = bg_a
        elif (v1 == 12 and v2 >= 7) or (v1 >= 10 and v2 >= 8):
            bg_color = bg_b
        elif (v1 >= 9 and v2 >= 6):
            bg_color = bg_c
        else:
            bg_color = bg_d

    return txt_color, bg_color


# 마크다운 색상 처리 헬퍼 (하트/다이아 = 숫자+문양 모두 빨간색)
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

# 1) 169 핸드 매트릭스 버튼 스타일링
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
                font-size: 0.88rem !important;
            }}
        """)

# 3) 무늬(Suit) 원클릭 변경 버튼 스타일링
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
# 3. 헬퍼 계산 함수
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


def get_action_recommendation(equity, pot, call_amount):
    pot = max(0.0, float(pot))
    call_amount = max(0.0, float(call_amount))
    pot_odds = call_amount / (pot + call_amount) if pot + call_amount > 0 else 0.0
        
    if call_amount == 0:
        if equity >= 0.70:
            return "베팅 / 레이즈", "action-raise", "상대 대비 압도적인 승률입니다. 벨류 베팅을 권장합니다.", pot_odds
        elif equity >= 0.45:
            return "체크 / 프리베팅", "action-check", "안정적인 승률입니다. 체크로 다음 카드를 확인하세요.", pot_odds
        else:
            return "체크", "action-check", "추가 비용이 들지 않으므로 체크합니다.", pot_odds
    else:
        if equity < pot_odds:
            return "폴드 권장", "action-fold", f"승률({equity*100:.1f}%)이 팟 오즈({pot_odds*100:.1f}%)보다 낮습니다.", pot_odds
        elif equity >= 0.75:
            return "올인 / 강한 레이즈", "action-allin", "높은 승률입니다. 팟을 크게 키우세요.", pot_odds
        elif equity >= pot_odds + 0.15:
            return "레이즈 검토", "action-raise", "팟 오즈 대비 승률 여유가 충분합니다.", pot_odds
        else:
            return "콜 검토", "action-call", "팟 오즈 대비 최소 승률 조건을 충족합니다.", pot_odds


# ==========================================
# 4. 메인 화면: 169 핸드 매트릭스
# ==========================================
st.title("♠️ 실시간 홀덤 승률 & 액션 어드바이저")

st.markdown(f"""
    <div style="font-size:0.85rem; margin-bottom:8px; color:{text_sub}; font-weight:bold;">
        <b>글씨 색상:</b> 
        <span style="color:{txt_pair};">파랑(페어)</span> | 
        <span style="color:{txt_suited};">초록(수딧)</span> | 
        <span style="color:{txt_off};">주황(오프수딧)</span> &nbsp;&nbsp;|&nbsp;&nbsp; 
        <b>배경 색상:</b> 
        <span style="background:{bg_s}; padding:2px 6px; border-radius:3px; color:#1e293b;">S급</span> 
        <span style="background:{bg_a}; padding:2px 6px; border-radius:3px; color:#1e293b;">A급</span> 
        <span style="background:{bg_b}; padding:2px 6px; border-radius:3px; color:#1e293b;">B급</span> 
        <span style="background:{bg_c}; padding:2px 6px; border-radius:3px; color:#1e293b;">C급</span> 
        <span style="background:{bg_d}; padding:2px 6px; border-radius:3px; color:#1e293b; border:1px solid #ccc;">D급</span>
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
# 5. 선택 핸드 및 원클릭 무늬 프리셋 (알파벳/숫자 포함 개별 색상 적용)
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
# 6. 원클릭 보드 선택 (알파벳/숫자 포함 개별 색상 적용)
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
# 7. 실시간 승률 계산 및 액션 추천
# ==========================================
st.markdown("---")

invalid_board_count = len(board_cards) not in (0, 3, 4, 5)

if invalid_board_count:
    st.warning("⚠️ 보드 카드는 **0장(프리플랍)**, **3장(플랍)**, **4장(턴)**, **5장(리버)** 조합일 때 정확히 계산됩니다.")
else:
    if st.button("🚀 실시간 승률 및 액션 확인", type="primary", use_container_width=True):
        try:
            with st.spinner("몬테카를로 승률 계산 중..."):
                hero_treys = [Card.new(c) for c in hero_cards]
                board_treys = [Card.new(c) for c in board_cards]
                
                equity, win_rate, tie_rate, loss_rate = calculate_monte_carlo_equity(
                    hero_treys, board_treys, opponents_count, sim_iterations
                )
                action, action_class, reason, pot_odds = get_action_recommendation(
                    equity, pot_size, call_amount
                )

            res1, res2, res3 = st.columns([1, 1, 1])
            res1.metric("최종 승률 (Equity)", f"{equity*100:.1f}%")
            res2.metric("순수 승리 확률", f"{win_rate*100:.1f}%")
            res3.metric("비길 확률 (Split)", f"{tie_rate*100:.1f}%")

            st.markdown(f"""
                <div class="action-card" style="margin-top:10px;">
                    <div style="color: {text_sub}; font-size: 0.9rem;">추천 액션</div>
                    <div class="action-title {action_class}">{action}</div>
                    <div style="color: {text_main}; font-size: 0.95rem; margin-top: 5px;">{reason}</div>
                </div>
            """, unsafe_allow_html=True)

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
