import random
import streamlit as st
import plotly.graph_objects as go
from treys import Card, Deck, Evaluator

# ==========================================
# 0. 페이지 기본 설정 및 테마 CSS
# ==========================================
st.set_page_config(
    page_title="텍사스 홀덤 실시간 승률 & 액션 어드바이저",
    page_icon="♠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 홀덤 스타일의 어두운 테마 및 커스텀 카드 UI 스타일
st.markdown("""
    <style>
    .main {
        background-color: #0e1117;
    }
    .card-badge {
        display: inline-block;
        padding: 6px 12px;
        font-size: 1.1rem;
        font-weight: bold;
        border-radius: 6px;
        margin: 2px;
        text-align: center;
        border: 1px solid #333;
    }
    .suit-s, .suit-c { background-color: #262626; color: #ffffff; }
    .suit-h, .suit-d { background-color: #3d0c0c; color: #ff4d4d; border: 1px solid #8b0000; }
    
    .action-card {
        background-color: #1a1e24;
        border-radius: 10px;
        padding: 20px;
        border: 2px solid #2d3748;
        text-align: center;
        margin-top: 10px;
    }
    .action-title {
        font-size: 1.8rem;
        font-weight: bold;
        margin-bottom: 5px;
    }
    .action-fold { color: #ff4d4d; }
    .action-check { color: #4dabf7; }
    .action-call { color: #fcc419; }
    .action-raise { color: #51cf66; }
    .action-allin { color: #ff922b; }
    </style>
""", unsafe_allow_html=True)

EVALUATOR = Evaluator()

RANKS = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"]
SUITS = ["s", "h", "d", "c"]
SUIT_SYMBOLS = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
SUIT_NAMES = {"s": "스페이드(♠)", "h": "하트(♥)", "d": "다이아(♦)", "c": "클로버(♣)"}


# ==========================================
# 1. 헬퍼 및 유틸리티 함수
# ==========================================
def format_card_html(card_code):
    """카드 코드를 색상 태그가 포함된 HTML 형태로 변환"""
    if not card_code or len(card_code) < 2:
        return ""
    rank = card_code[0].replace("T", "10")
    suit = card_code[1]
    symbol = SUIT_SYMBOLS.get(suit, "")
    css_class = f"suit-{suit}"
    return f'<span class="card-badge {css_class}">{rank}{symbol}</span>'


def hand_type(r1, r2):
    """169개 프리플랍 표 표기법 변환"""
    i1, i2 = RANKS.index(r1), RANKS.index(r2)
    if i1 == i2:
        return r1 + r2
    elif i1 < i2:
        return r1 + r2 + "s"
    else:
        return r2 + r1 + "o"


def calculate_monte_carlo_equity(hero_cards, board_cards, opponents_count, iterations=3000):
    """
    Treys Evaluator 기반 몬테카를로 승률 산출 함수
    Treys Evaluator 점수는 낮을수록 높은 족보 (1 = 로열 플러시)
    """
    known_cards = hero_cards + board_cards
    full_deck = Deck.GetFullDeck()
    deck = [c for c in full_deck if c not in known_cards]
    
    missing_board_count = 5 - len(board_cards)
    draw_count = missing_board_count + (opponents_count * 2)
    
    wins = 0.0
    ties = 0.0
    losses = 0.0
    
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
        
        if hero_score < best_opp_score:  # Hero 승리
            wins += 1.0
        elif hero_score == best_opp_score:  # 타이 (팟 분할)
            tying_count = opp_scores.count(hero_score) + 1
            ties += (1.0 / tying_count)
        else:
            losses += 1.0
            
    equity = (wins + ties) / iterations
    win_rate = wins / iterations
    tie_rate = ties / iterations
    loss_rate = (iterations - wins - ties) / iterations
    
    return equity, win_rate, tie_rate, loss_rate


def get_action_recommendation(equity, pot, call_amount):
    """
    승률과 팟 오즈 기반 실시간 액션 추천 알고리즘
    """
    pot = max(0.0, float(pot))
    call_amount = max(0.0, float(call_amount))
    
    if pot + call_amount > 0:
        pot_odds = call_amount / (pot + call_amount)
    else:
        pot_odds = 0.0
        
    if call_amount == 0:
        if equity >= 0.70:
            return "베팅 / 레이즈", "action-raise", "상대 대비 압도적인 승률입니다. 벨류 베팅을 적극 권장합니다.", pot_odds
        elif equity >= 0.45:
            return "체크 / 프리베팅", "action-check", "안정적인 승률입니다. 체크로 보드를 확인하거나 플롯 베팅을 시도하세요.", pot_odds
        else:
            return "체크", "action-check", "추가 비용이 들지 않습니다. 무료로 다음 카드를 확인하세요.", pot_odds
    else:
        if equity < pot_odds:
            return "폴드 권장", "action-fold", f"승률({equity*100:.1f}%)이 팟 오즈({pot_odds*100:.1f}%)보다 낮아 장기적으로 손해입니다.", pot_odds
        elif equity >= 0.75:
            return "올인 / 강한 레이즈", "action-allin", "높은 승률과 기댓값을 가집니다. 올인 또는 강한 레이즈로 팟을 키우세요.", pot_odds
        elif equity >= pot_odds + 0.15:
            return "레이즈 검토", "action-raise", "팟 오즈 대비 승률 여유가 충분합니다. 주도권을 가져오기 위한 레이즈를 고려하세요.", pot_odds
        else:
            return "콜 검토", "action-call", "팟 오즈 대비 최소 승률 조건은 충족하지만, 이익 폭이 크지 않습니다.", pot_odds


# ==========================================
# 2. 사이드바: 기본 플레이 설정
# ==========================================
st.sidebar.title("♠️ 옵션 & 베팅 설정")
st.sidebar.markdown("---")

opponents_count = st.sidebar.slider("상대 플레이어 수 (Opponents)", min_value=1, max_value=8, value=2)

st.sidebar.markdown("### 💰 팟 및 베팅 정보 (선택)")
pot_size = st.sidebar.number_input("현재 팟 금액 ($)", min_value=0.0, value=100.0, step=10.0)
call_amount = st.sidebar.number_input("콜 필요 금액 ($)", min_value=0.0, value=20.0, step=5.0)

st.sidebar.markdown("---")
sim_iterations = st.sidebar.select_slider(
    "정밀도 (시뮬레이션 횟수)",
    options=[1000, 2500, 5000, 10000],
    value=2500,
    help="횟수가 높을수록 정밀하지만 계산 시간이 약간 늘어납니다."
)


# ==========================================
# 3. 메인 인터페이스
# ==========================================
st.title("♠️ 텍사스 홀덤 실시간 승률 & 액션 어드바이저")
st.caption("복잡한 게임 진행 없이 핸드와 보드 카드 선택만으로 오류 없이 빠르게 승률과 추천 액션을 제공합니다.")

# 세션 상태 초기화
if "hero_card1" not in st.session_state:
    st.session_state.hero_card1 = "As"
if "hero_card2" not in st.session_state:
    st.session_state.hero_card2 = "Ks"

tab_matrix, tab_custom = st.tabs(["🔥 169 핸드 표로 빠른 선택", "🃏 직접 카드 선택 (Rank & Suit)"])

# --- TAB 1: 169 매트릭스 선택 ---
with tab_matrix:
    st.markdown("##### 핸드 매트릭스 (클릭하여 빠른 적용)")
    st.caption("🟦 페어 | 🟩 수딧(같은 무늬) | 🟧 오프수딧(다른 무늬)")
    
    # 13x13 매트릭스 그리드 생성
    matrix_cols = st.columns([0.6] + [1]*13)
    matrix_cols[0].write("")
    for j, r in enumerate(RANKS):
        matrix_cols[j+1].markdown(f"**{r}**")
        
    for i, r1 in enumerate(RANKS):
        m_row = st.columns([0.6] + [1]*13)
        m_row[0].markdown(f"**{r1}**")
        for j, r2 in enumerate(RANKS):
            ht = hand_type(r1, r2)
            prefix = "🟦" if r1 == r2 else ("🟩" if RANKS.index(r1) < RANKS.index(r2) else "🟧")
            
            if m_row[j+1].button(f"{prefix}{ht}", key=f"mat_{r1}_{r2}", use_container_width=True):
                if r1 == r2:
                    st.session_state.hero_card1 = f"{r1}s"
                    st.session_state.hero_card2 = f"{r2}c"
                elif RANKS.index(r1) < RANKS.index(r2):  # Suited
                    st.session_state.hero_card1 = f"{r1}s"
                    st.session_state.hero_card2 = f"{r2}s"
                else:  # Offsuit
                    st.session_state.hero_card1 = f"{r1}s"
                    st.session_state.hero_card2 = f"{r2}h"
                st.rerun()

# --- TAB 2: 직접 정밀 선택 ---
with tab_custom:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("내 첫 번째 카드")
        r1 = st.selectbox("숫자 (Rank 1)", RANKS, index=RANKS.index(st.session_state.hero_card1[0]))
        s1 = st.selectbox("무늬 (Suit 1)", list(SUIT_NAMES.keys()), format_func=lambda x: SUIT_NAMES[x], index=SUITS.index(st.session_state.hero_card1[1]))
        st.session_state.hero_card1 = f"{r1}{s1}"
        
    with c2:
        st.subheader("내 두 번째 카드")
        r2 = st.selectbox("숫자 (Rank 2)", RANKS, index=RANKS.index(st.session_state.hero_card2[0]))
        s2 = st.selectbox("무늬 (Suit 2)", list(SUIT_NAMES.keys()), format_func=lambda x: SUIT_NAMES[x], index=SUITS.index(st.session_state.hero_card2[1]), key="s2_select")
        st.session_state.hero_card2 = f"{r2}{s2}"

st.markdown("---")


# ==========================================
# 4. 커뮤니티 보드 카드 선택 (Flop, Turn, River)
# ==========================================
st.subheader("🃏 커뮤니티 보드 카드 선택")

# 사용 불가능한 카드 목록 생성용 전체 카드 리스트
all_card_codes = [f"{r}{s}" for r in RANKS for s in SUITS]

b_col1, b_col2, b_col3, b_col4, b_col5 = st.columns(5)

board_inputs = []

def card_selector(label_name, key_name, default_idx=0):
    opts = ["선택 안함"] + [f"{r}{SUIT_SYMBOLS[s]}" for r in RANKS for s in SUITS]
    selected = st.selectbox(label_name, opts, index=default_idx, key=key_name)
    if selected != "선택 안함":
        rank = selected[:-1].replace("10", "T")
        sym = selected[-1]
        suit = [k for k, v in SUIT_SYMBOLS.items() if v == sym][0]
        return f"{rank}{suit}"
    return None

with b_col1:
    f1 = card_selector("플랍 1", "f1_select")
with b_col2:
    f2 = card_selector("플랍 2", "f2_select")
with b_col3:
    f3 = card_selector("플랍 3", "f3_select")
with b_col4:
    t1 = card_selector("턴 (Turn)", "t1_select")
with b_col5:
    r1_card = card_selector("리버 (River)", "r1_select")

raw_board = [f1, f2, f3, t1, r1_card]
board_cards = [c for c in raw_board if c is not None]

# 선택 상태 요약 디스플레이
hero_cards = [st.session_state.hero_card1, st.session_state.hero_card2]

st.markdown("### 📌 현재 선택된 상태")
h_html = "".join([format_card_html(c) for c in hero_cards])
b_html = "".join([format_card_html(c) for c in board_cards]) if board_cards else "<span style='color:gray;'>프리플랍 (보드 카드 없음)</span>"

st.markdown(f"**내 핸드:** {h_html} &nbsp;&nbsp;|&nbsp;&nbsp; **보드 카드:** {b_html}", unsafe_allow_html=True)


# ==========================================
# 5. 검증 및 승률 계산 실행
# ==========================================
st.markdown("---")

all_selected = hero_cards + board_cards
has_duplicates = len(all_selected) != len(set(all_selected))
invalid_board_count = len(board_cards) not in (0, 3, 4, 5)

if has_duplicates:
    st.error("⚠️ 중복된 카드가 선택되었습니다. 내 핸드 및 보드 카드가 서로 겹치지 않게 수정해 주세요.")
elif invalid_board_count:
    st.warning("⚠️ 보드 카드는 **0장 (프리플랍)**, **3장 (플랍)**, **4장 (턴)**, **5장 (리버)** 중 하나여야 합니다.")
else:
    if st.button("🚀 실시간 승률 계산 및 액션 추천", type="primary", use_container_width=True):
        try:
            with st.spinner("몬테카를로 시뮬레이션 계산 중..."):
                hero_treys = [Card.new(c) for c in hero_cards]
                board_treys = [Card.new(c) for c in board_cards]
                
                equity, win_rate, tie_rate, loss_rate = calculate_monte_carlo_equity(
                    hero_treys, board_treys, opponents_count, sim_iterations
                )
                
                action, action_class, reason, pot_odds = get_action_recommendation(
                    equity, pot_size, call_amount
                )

            # 결과 디스플레이
            st.subheader("📊 승률 계산 결과")
            
            res_col1, res_col2, res_col3, res_col4 = st.columns(4)
            res_col1.metric("최종 승률 (Equity)", f"{equity*100:.1f}%")
            res_col2.metric("순수 승리 확률", f"{win_rate*100:.1f}%")
            res_col3.metric("비길 확률 (Split)", f"{tie_rate*100:.1f}%")
            res_col4.metric("패배 확률", f"{loss_rate*100:.1f}%")
            
            # 추천 액션 메인 패널
            st.markdown(f"""
                <div class="action-card">
                    <div style="color: #8892b0; font-size: 1rem;">추천 행동 (Recommended Action)</div>
                    <div class="action-title {action_class}">{action}</div>
                    <div style="color: #e6f1ff; font-size: 1.05rem; margin-top: 10px;">{reason}</div>
                </div>
            """, unsafe_allow_html=True)
            
            # 파이 차트 시각화
            fig = go.Figure(data=[go.Pie(
                labels=['승리', '비김', '패배'],
                values=[win_rate*100, tie_rate*100, loss_rate*100],
                hole=.4,
                marker_colors=['#51cf66', '#fcc419', '#ff4d4d']
            )])
            fig.update_layout(
                title_text="승/무/패 예측 비율",
                template="plotly_dark",
                height=300,
                margin=dict(l=20, r=20, t=40, b=20)
            )
            st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error(f"계산 중 오류가 발생했습니다: {str(e)}")
