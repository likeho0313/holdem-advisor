import random
import streamlit as st
import plotly.graph_objects as go
from treys import Card, Deck, Evaluator

# ==========================================
# 0. 페이지 기본 설정 및 모바일/가로모드 대응 CSS
# ==========================================
st.set_page_config(
    page_title="텍사스 홀덤 실시간 승률 & 액션 어드바이저",
    page_icon="♠️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

RANKS = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"]
SUITS = ["s", "h", "d", "c"]
SUIT_SYMBOLS = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
SUIT_NAMES = {"s": "스페이드(♠)", "h": "하트(♥)", "d": "다이아(♦)", "c": "클로버(♣)"}

EVALUATOR = Evaluator()

# ==========================================
# 1. 헬퍼 함수 & 핸드 승률 구간별 색상 정의
# ==========================================
def hand_type(r1, r2):
    """169개 프리플랍 명칭 산출 (예: AA, AKs, AKo)"""
    i1, i2 = RANKS.index(r1), RANKS.index(r2)
    if i1 == i2:
        return r1 + r2
    elif i1 < i2:
        return r1 + r2 + "s"
    else:
        return r2 + r1 + "o"

def get_hand_colors(r1, r2):
    """
    1) 글자 색상: 페어(파랑), 수딧(초록), 오프수딧(주황)
    2) 배경 색상: 헤즈업 프리플랍 추정 승률 구간별 (S, A, B, C, D 티어)
    """
    i1, i2 = RANKS.index(r1), RANKS.index(r2)
    
    # 1. 글씨 색상
    if i1 == i2:
        text_color = "#60a5fa"  # 페어: 파랑계열
    elif i1 < i2:
        text_color = "#4ade80"  # 수딧(같은 무늬): 초록계열
    else:
        text_color = "#fb923c"  # 오프수딧(다른 무늬): 주황계열

    # 2. 배경 색상 (승률 티어)
    v1, v2 = 12 - i1, 12 - i2
    if i1 > i2:
        v1, v2 = v2, v1
    
    if i1 == i2:  # 페어
        if v1 >= 9:      # TT ~ AA
            bg_color = "#14532d"  # S티어: 짙은 에메랄드
        elif v1 >= 6:    # 77 ~ 99
            bg_color = "#1e3a8a"  # A티어: 짙은 네이비
        elif v1 >= 3:    # 44 ~ 66
            bg_color = "#713f12"  # B티어: 브론즈
        else:            # 22 ~ 33
            bg_color = "#334155"  # C티어: 슬레이트
    elif i1 < i2: # 수딧
        if (v1 >= 11 and v2 >= 10) or (v1 == 12 and v2 >= 8): # AKs, AQs, AJs, ATs, KQs
            bg_color = "#14532d"  # S티어
        elif (v1 >= 10 and v2 >= 8) or (v1 == 12 and v2 >= 4) or (v1 >= 8 and v2 >= 7 and v1 - v2 == 1):
            bg_color = "#1e3a8a"  # A티어
        elif (v1 >= 8 and v2 >= 5) or (v1 - v2 <= 2 and v2 >= 4):
            bg_color = "#713f12"  # B티어
        elif v1 >= 7:
            bg_color = "#334155"  # C티어
        else:
            bg_color = "#0f172a"  # D티어
    else:        # 오프수딧
        if (v1 == 12 and v2 >= 10) or (v1 == 11 and v2 == 10): # AKo, AQo, AJo, KQo
            bg_color = "#1e3a8a"  # A티어
        elif (v1 == 12 and v2 >= 7) or (v1 >= 10 and v2 >= 8): # ATo, KJo, QJo
            bg_color = "#713f12"  # B티어
        elif (v1 >= 9 and v2 >= 6):
            bg_color = "#334155"  # C티어
        else:
            bg_color = "#0f172a"  # D티어

    return text_color, bg_color

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
# 2. 세션 상태 초기화 및 고유 키 기반 CSS 생성
# ==========================================
if "hero_card1" not in st.session_state:
    st.session_state.hero_card1 = "As"
if "hero_card2" not in st.session_state:
    st.session_state.hero_card2 = "Ks"

# ★ Streamlit 버튼 고유 키(.st-key-mat_{r1}_{r2}) 기반 타겟팅 CSS ★
dynamic_button_styles = []
for r1 in RANKS:
    for r2 in RANKS:
        ht = hand_type(r1, r2)
        text_color, bg_color = get_hand_colors(r1, r2)
        
        h1, h2 = st.session_state.hero_card1, st.session_state.hero_card2
        selected_ht = hand_type(h1[0], h2[0])
        is_selected = (ht == selected_ht)
        
        if is_selected:
            dynamic_button_styles.append(f"""
                div.st-key-mat_{r1}_{r2} > button,
                div.st-key-mat_{r1}_{r2} > button * {{
                    background-color: #dc2626 !important;
                    color: #ffffff !important;
                    border: 2px solid #f59e0b !important;
                    font-weight: bold !important;
                }}
            """)
        else:
            dynamic_button_styles.append(f"""
                div.st-key-mat_{r1}_{r2} > button,
                div.st-key-mat_{r1}_{r2} > button * {{
                    background-color: {bg_color} !important;
                    color: {text_color} !important;
                    border: 1px solid #334155 !important;
                }}
            """)

# UI 및 모바일 가로모드 전용 최적화 CSS
st.markdown(f"""
    <style>
    /* 기본 테마 무관 어두운 배경 고정 */
    .stApp {{ background-color: #0e1117; color: #ffffff; }}
    
    /* 13x13 매트릭스 버튼 간격 축소 및 모바일 대응 */
    div[data-testid="stHorizontal"] > div {{
        padding: 0px 1px !important;
    }}
    .stButton button {{
        width: 100% !important;
        padding: 3px 0px !important;
        font-size: 0.80rem !important;
        min-height: 38px !important;
        margin: 0px !important;
        border-radius: 4px !important;
    }}
    
    {" ".join(dynamic_button_styles)}

    /* 카드 태그 스타일 */
    .card-badge {{
        display: inline-block;
        padding: 4px 8px;
        font-size: 1.05rem;
        font-weight: bold;
        border-radius: 5px;
        margin: 1px;
    }}
    .suit-s, .suit-c {{ background-color: #1e293b; color: #ffffff; border: 1px solid #475569; }}
    .suit-h, .suit-d {{ background-color: #450a0a; color: #f87171; border: 1px solid #991b1b; }}
    
    .action-card {{
        background-color: #1e293b;
        border-radius: 8px;
        padding: 15px;
        border: 1px solid #475569;
        text-align: center;
    }}
    .action-title {{ font-size: 1.5rem; font-weight: bold; }}
    .action-fold {{ color: #f87171; }}
    .action-check {{ color: #38bdf8; }}
    .action-call {{ color: #facc15; }}
    .action-raise {{ color: #4ade80; }}
    .action-allin {{ color: #fb923c; }}

    /* 모바일 가로모드 (Landscape) UI 최적화 */
    @media screen and (max-height: 600px), (max-width: 920px) {{
        .block-container {{
            padding-top: 0.5rem !important;
            padding-bottom: 0.5rem !important;
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
        }}
        .stButton button {{
            padding: 1px 0px !important;
            font-size: 0.72rem !important;
            min-height: 28px !important;
        }}
        .card-badge {{
            padding: 2px 5px !important;
            font-size: 0.85rem !important;
        }}
        .action-card {{ padding: 8px !important; }}
        .action-title {{ font-size: 1.2rem !important; }}
    }}
    </style>
""", unsafe_allow_html=True)


# ==========================================
# 3. 사이드바 설정
# ==========================================
st.sidebar.title("♠️ 팟 & 게임 옵션")
opponents_count = st.sidebar.slider("상대 플레이어 수", min_value=1, max_value=8, value=2)
pot_size = st.sidebar.number_input("현재 팟 금액 ($)", min_value=0.0, value=100.0, step=10.0)
call_amount = st.sidebar.number_input("콜 필요 금액 ($)", min_value=0.0, value=20.0, step=5.0)
sim_iterations = st.sidebar.select_slider("정밀도 (시뮬레이션)", options=[1000, 2500, 5000], value=2500)


# ==========================================
# 4. 메인 UI 및 169 핸드 표
# ==========================================
st.title("♠️ 실시간 홀덤 승률 & 액션 어드바이저")

# 범례 디스플레이
st.markdown("""
    <div style="font-size:0.82rem; margin-bottom:8px;">
        <b>글씨 색상:</b> <span style="color:#60a5fa; font-weight:bold;">파랑(페어)</span> | 
        <span style="color:#4ade80; font-weight:bold;">초록(수딧)</span> | 
        <span style="color:#fb923c; font-weight:bold;">주황(오프수딧)</span> &nbsp;&nbsp;|&nbsp;&nbsp; 
        <b>배경 색상:</b> 
        <span style="background:#14532d; padding:2px 6px; border-radius:3px; color:#fff;">S급</span> 
        <span style="background:#1e3a8a; padding:2px 6px; border-radius:3px; color:#fff;">A급</span> 
        <span style="background:#713f12; padding:2px 6px; border-radius:3px; color:#fff;">B급</span> 
        <span style="background:#334155; padding:2px 6px; border-radius:3px; color:#fff;">C급</span> 
        <span style="background:#0f172a; padding:2px 6px; border-radius:3px; color:#fff;">D급</span>
    </div>
""", unsafe_allow_html=True)

# 13x13 핸드 표 생성
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
            if r1 == r2:  # Pair
                st.session_state.hero_card1 = f"{r1}s"
                st.session_state.hero_card2 = f"{r2}h"
            elif RANKS.index(r1) < RANKS.index(r2):  # Suited
                st.session_state.hero_card1 = f"{r1}s"
                st.session_state.hero_card2 = f"{r2}s"
            else:  # Offsuit
                st.session_state.hero_card1 = f"{r1}s"
                st.session_state.hero_card2 = f"{r2}h"
            st.rerun()


# ==========================================
# 5. 선택된 핸드 & 직관적인 원클릭 무늬(Suit) 변경 패널
# ==========================================
st.markdown("---")
h1, h2 = st.session_state.hero_card1, st.session_state.hero_card2
r1, r2 = h1[0], h2[0]
s1, s2 = h1[1], h2[1]
ht = hand_type(r1, r2)

hero_cards = [h1, h2]
h_html = "".join([format_card_html(c) for c in hero_cards])

st.markdown(f"### 📌 선택된 내 핸드: {h_html} `({ht})`", unsafe_allow_html=True)

# ★ 요구사항: 수딧 / 오프수딧 / 페어의 무늬를 원클릭으로 변경하는 직관적 패널 ★
st.write("⚡ **무늬(Suit) 원클릭 변경:**")

if r1 == r2:  # 페어 (Pair)
    pair_combos = [("s", "h"), ("s", "d"), ("s", "c"), ("h", "d"), ("h", "c"), ("d", "c")]
    p_cols = st.columns(6)
    for idx, (p1, p2) in enumerate(pair_combos):
        btn_label = f"{SUIT_SYMBOLS[p1]}{SUIT_SYMBOLS[p2]} ({r1}{SUIT_SYMBOLS[p1]} {r2}{SUIT_SYMBOLS[p2]})"
        if p_cols[idx].button(btn_label, key=f"quick_pair_{p1}_{p2}", use_container_width=True):
            st.session_state.hero_card1 = f"{r1}{p1}"
            st.session_state.hero_card2 = f"{r2}{p2}"
            st.rerun()

elif s1 == s2:  # 수딧 (Suited)
    s_cols = st.columns(4)
    for idx, suit in enumerate(SUITS):
        btn_label = f"{SUIT_SYMBOLS[suit]}{SUIT_SYMBOLS[suit]} ({r1}{SUIT_SYMBOLS[suit]} {r2}{SUIT_SYMBOLS[suit]})"
        if s_cols[idx].button(btn_label, key=f"quick_suited_{suit}", use_container_width=True):
            st.session_state.hero_card1 = f"{r1}{suit}"
            st.session_state.hero_card2 = f"{r2}{suit}"
            st.rerun()

else:  # 오프수딧 (Offsuit)
    off_combos = [("s", "h"), ("s", "d"), ("s", "c"), ("h", "d"), ("h", "c"), ("d", "c")]
    o_cols = st.columns(6)
    for idx, (p1, p2) in enumerate(off_combos):
        btn_label = f"{SUIT_SYMBOLS[p1]}{SUIT_SYMBOLS[p2]} ({r1}{SUIT_SYMBOLS[p1]} {r2}{SUIT_SYMBOLS[p2]})"
        if o_cols[idx].button(btn_label, key=f"quick_off_{p1}_{p2}", use_container_width=True):
            st.session_state.hero_card1 = f"{r1}{p1}"
            st.session_state.hero_card2 = f"{r2}{p2}"
            st.rerun()


# ==========================================
# 6. 커뮤니티 보드 선택 (내 핸드 카드 자동 제외 & 동적 동기화)
# ==========================================
st.markdown("---")
st.subheader("🃏 보드 카드 선택 (플랍 · 턴 · 리버)")

# ★ 요구사항: 내 핸드 카드는 보드 선택에서 완전 제외 ★
available_deck = [f"{r}{s}" for r in RANKS for s in SUITS if f"{r}{s}" not in hero_cards]

b_col1, b_col2, b_col3, b_col4, b_col5 = st.columns(5)

def card_selector(label_name, key_name):
    options = ["선택 안함"] + [f"{c[0].replace('T','10')}{SUIT_SYMBOLS[c[1]]}" for c in available_deck]
    
    # 이전 선택값이 내 카드 변경으로 인해 불가능해진 경우 초기화
    curr_val = st.session_state.get(key_name, "선택 안함")
    if curr_val not in options:
        curr_val = "선택 안함"
        
    selected = st.selectbox(label_name, options, index=options.index(curr_val), key=key_name)
    if selected != "선택 안함":
        rank = selected[:-1].replace("10", "T")
        sym = selected[-1]
        suit = [k for k, v in SUIT_SYMBOLS.items() if v == sym][0]
        return f"{rank}{suit}"
    return None

with b_col1: f1 = card_selector("플랍 1", "f1_sel")
with b_col2: f2 = card_selector("플랍 2", "f2_sel")
with b_col3: f3 = card_selector("플랍 3", "f3_sel")
with b_col4: t1 = card_selector("턴 (Turn)", "t1_sel")
with b_col5: r1_card = card_selector("리버 (River)", "r1_sel")

raw_board = [f1, f2, f3, t1, r1_card]
board_cards = [c for c in raw_board if c is not None]

b_html = "".join([format_card_html(c) for c in board_cards]) if board_cards else "<span style='color:gray;'>프리플랍 (보드 없음)</span>"
st.markdown(f"**현재 보드 카드:** {b_html}", unsafe_allow_html=True)


# ==========================================
# 7. 승률 계산 및 액션 추천
# ==========================================
has_board_duplicates = len(board_cards) != len(set(board_cards))
invalid_board_count = len(board_cards) not in (0, 3, 4, 5)

if has_board_duplicates:
    st.error("⚠️ 보드 카드 중 중복 선택된 카드가 있습니다.")
elif invalid_board_count:
    st.warning("⚠️ 보드 카드는 **0장(프리플랍)**, **3장(플랍)**, **4장(턴)**, **5장(리버)** 중에서 선택하세요.")
else:
    if st.button("🚀 실시간 승률 및 액션 확인", type="primary", use_container_width=True):
        try:
            with st.spinner("승률 시뮬레이션 계산 중..."):
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
                    <div style="color: #94a3b8; font-size: 0.9rem;">추천 액션</div>
                    <div class="action-title {action_class}">{action}</div>
                    <div style="color: #e2e8f0; font-size: 0.95rem; margin-top: 5px;">{reason}</div>
                </div>
            """, unsafe_allow_html=True)

            fig = go.Figure(data=[go.Pie(
                labels=['승리', '비김', '패배'],
                values=[win_rate*100, tie_rate*100, loss_rate*100],
                hole=.4,
                marker_colors=['#4ade80', '#facc15', '#f87171']
            )])
            fig.update_layout(
                template="plotly_dark",
                height=240,
                margin=dict(l=10, r=10, t=20, b=20),
                showlegend=True
            )
            st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error(f"계산 중 에러가 발생했습니다: {str(e)}")
