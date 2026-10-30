import random
import itertools
from collections import Counter
import streamlit as st
import plotly.graph_objects as go
from treys import Card, Deck, Evaluator

# ==========================================
# 0. 페이지 기본 설정 및 초기 세션 상태
# ==========================================
st.set_page_config(
    page_title="텍사스 홀덤 실시간 승률 & 모의게임 어드바이저",
    page_icon="♠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

RANKS = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"]
SUITS = ["s", "h", "d", "c"]
SUIT_SYMBOLS = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}

RANK_MAP = {'A': 14, 'K': 13, 'Q': 12, 'J': 11, 'T': 10, '9': 9, '8': 8, '7': 7, '6': 6, '5': 5, '4': 4, '3': 3, '2': 2}
RANK_NAME = {14: 'A', 13: 'K', 12: 'Q', 11: 'J', 10: '10', 9: '9', 8: '8', 7: '7', 6: '6', 5: '5', 4: '4', 3: '3', 2: '2'}

EVALUATOR = Evaluator()

# --- [어드바이저 세션 상태 초기화] ---
if "hero_card1" not in st.session_state:
    st.session_state.hero_card1 = "As"
if "hero_card2" not in st.session_state:
    st.session_state.hero_card2 = "Ks"
if "board_cards" not in st.session_state:
    st.session_state.board_cards = []
if "bet_ratio_pct" not in st.session_state:
    st.session_state.bet_ratio_pct = 25.0

# --- [모의게임 세션 상태 초기화] ---
if "mg_user_chips" not in st.session_state:
    st.session_state.mg_user_chips = 1000
if "mg_opp_chips" not in st.session_state:
    st.session_state.mg_opp_chips = 1000
if "mg_pot" not in st.session_state:
    st.session_state.mg_pot = 0
if "mg_stage" not in st.session_state:
    st.session_state.mg_stage = "IDLE"  # IDLE, PREFLOP, FLOP, TURN, RIVER, SHOWDOWN
if "mg_hero_cards" not in st.session_state:
    st.session_state.mg_hero_cards = []
if "mg_opp_cards" not in st.session_state:
    st.session_state.mg_opp_cards = []
if "mg_board_cards" not in st.session_state:
    st.session_state.mg_board_cards = []
if "mg_deck" not in st.session_state:
    st.session_state.mg_deck = []
if "mg_user_bet" not in st.session_state:
    st.session_state.mg_user_bet = 0
if "mg_opp_bet" not in st.session_state:
    st.session_state.mg_opp_bet = 0
if "mg_result_msg" not in st.session_state:
    st.session_state.mg_result_msg = ""
if "mg_last_action" not in st.session_state:
    st.session_state.mg_last_action = ""


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
# 2. 사이드바: 옵션 및 사용 설명서
# ==========================================
opponents_count = st.sidebar.slider("상대 플레이어 수 (어드바이저 모드)", min_value=1, max_value=9, value=2)
sim_iterations = st.sidebar.select_slider("정밀도 (시뮬레이션)", options=[1000, 2500, 5000], value=2500)

st.sidebar.markdown("---")
st.sidebar.title("⚙️ 설정 & UI 테마")

theme_mode = st.sidebar.radio("🎨 UI 테마 선택", ["☀️ 라이트 모드", "🌙 다크 모드"], index=0)
is_dark = (theme_mode == "🌙 다크 모드")

with st.sidebar.expander("📖 서비스 사용 설명서", expanded=True):
    st.markdown("""
    **📊 실시간 승률 어드바이저 탭**
    1. 169 매트릭스에서 핸드를 선택하고 무늬 조합을 고릅니다.
    2. 커뮤니티 보드(플랍/턴/리버) 카드를 추가합니다.
    3. 상대 베팅 크기를 선택하여 '내 승률'과 '콜 필요 승률'을 실시간 비교합니다.

    **🎮 모의게임 (홀덤 연습) 탭**
    1. **새 판 시작**을 눌러 1000칩으로 AI 상대와 1:1 홀덤을 진행합니다.
    2. 프리플랍, 플랍, 턴, 리버 단계를 거치며 **Check / Call / Raise / Fold**를 결정합니다.
    3. 쇼다운 시 승리하면 팟 전체 칩을 획득합니다!
    """)


# ==========================================
# 3. 테마별 색상 및 전역 CSS 주입
# ==========================================
if is_dark:
    app_bg = "#0f172a"
    card_bg = "#1e293b"
    text_main = "#f8fafc"
    text_sub = "#94a3b8"
    border_col = "#334155"
    
    bg_s, bg_a, bg_b, bg_c, bg_d = "#14532d", "#1e3a8a", "#713f12", "#581c87", "#1e293b"
    badge_txt = "#ffffff"
    txt_pair, txt_suited, txt_off = "#93c5fd", "#86efac", "#fdba74"
    btn_preset_active_bg, btn_preset_active_txt = "#3b82f6", "#ffffff"
    btn_preset_inactive_bg, btn_preset_inactive_txt = "#1e293b", "#f8fafc"
else:
    app_bg = "#f8fafc"
    card_bg = "#ffffff"
    text_main = "#0f172a"
    text_sub = "#475569"
    border_col = "#cbd5e1"
    
    bg_s, bg_a, bg_b, bg_c, bg_d = "#a7f3d0", "#bae6fd", "#fef08a", "#e9d5ff", "#ffffff"
    badge_txt = "#0f172a"
    txt_pair, txt_suited, txt_off = "#1d4ed8", "#15803d", "#c2410c"
    btn_preset_active_bg, btn_preset_active_txt = "#2563eb", "#ffffff"
    btn_preset_inactive_bg, btn_preset_inactive_txt = "#ffffff", "#0f172a"


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
    if ht in TIER_S: return txt_color, bg_s
    elif ht in TIER_A: return txt_color, bg_a
    elif ht in TIER_B: return txt_color, bg_b
    elif ht in TIER_C: return txt_color, bg_c
    else: return txt_color, bg_d


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


def format_card_html(card_code):
    if not card_code or len(card_code) < 2:
        return ""
    rank = card_code[0].replace("T", "10")
    suit = card_code[1]
    symbol = SUIT_SYMBOLS.get(suit, "")
    css_class = f"suit-{suit}"
    return f'<span class="card-badge {css_class}">{rank}{symbol}</span>'


# 한국식 7포커 족보 계산 함수
def eval_5cards_korean(combo):
    ranks = sorted([RANK_MAP[c[0]] for c in combo], reverse=True)
    suits = [c[1] for c in combo]
    is_flush = (len(set(suits)) == 1)
    
    is_mountain = (ranks == [14, 13, 12, 11, 10])
    is_back_straight = (ranks == [14, 5, 4, 3, 2])
    is_reg_straight = (ranks[0]-ranks[1]==1 and ranks[1]-ranks[2]==1 and ranks[2]-ranks[3]==1 and ranks[3]-ranks[4]==1)
    
    counts = Counter(ranks)
    freq = sorted([(cnt, r) for r, cnt in counts.items()], key=lambda x: (x[0], x[1]), reverse=True)
    
    if is_flush and is_mountain: return (13, ranks), "👑 로얄 스트레이트 플러쉬"
    elif is_flush and is_back_straight: return (12, ranks), "🌈 백 스트레이트 플러쉬"
    elif is_flush and is_reg_straight: return (11, ranks[0]), f"🔥 스트레이트 플러쉬 ({RANK_NAME[ranks[0]]}-High)"
    elif freq[0][0] == 4: return (10, freq[0][1], freq[1][1]), f"💥 포카드 ({RANK_NAME[freq[0][1]]})"
    elif freq[0][0] == 3 and freq[1][0] == 2: return (9, freq[0][1], freq[1][1]), f"🏠 풀하우스 ({RANK_NAME[freq[0][1]]} & {RANK_NAME[freq[1][1]]})"
    elif is_flush: return (8, ranks), f"🎨 플러쉬 ({RANK_NAME[ranks[0]]}-High)"
    elif is_mountain: return (7, 14), "⛰️ 마운틴 (10, J, Q, K, A)"
    elif is_back_straight: return (6, 5), "👶 백스트레이트 (A, 2, 3, 4, 5)"
    elif is_reg_straight: return (5, ranks[0]), f"📏 스트레이트 ({RANK_NAME[ranks[0]]}-High)"
    elif freq[0][0] == 3: return (4, freq[0][1], [f[1] for f in freq[1:]]), f"☘️ 트리플 ({RANK_NAME[freq[0][1]]})"
    elif freq[0][0] == 2 and freq[1][0] == 2: return (3, freq[0][1], freq[1][1], freq[2][1]), f"✌️ 투 페어 ({RANK_NAME[freq[0][1]]} & {RANK_NAME[freq[1][1]]})"
    elif freq[0][0] == 2: return (2, freq[0][1], [f[1] for f in freq[1:]]), f"1️⃣ 원 페어 ({RANK_NAME[freq[0][1]]})"
    else: return (1, ranks), f"🃏 노 페어 ({RANK_NAME[ranks[0]]}-High)"


def get_best_korean_hand(hero_cards, board_cards):
    all_cards = hero_cards + board_cards
    if len(all_cards) < 5: return "보드 카드를 더 선택해주세요"
    best_score = None
    best_name = ""
    for combo in itertools.combinations(all_cards, 5):
        score, name = eval_5cards_korean(combo)
        if best_score is None or score > best_score:
            best_score = score
            best_name = name
    return best_name


def calculate_monte_carlo_equity(hero_cards, board_cards, opponents_count, iterations=2500):
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
        if hero_score < best_opp_score: wins += 1.0
        elif hero_score == best_opp_score: ties += (1.0 / (opp_scores.count(hero_score) + 1))
        else: losses += 1.0
    equity = (wins + ties) / iterations
    return equity, wins/iterations, ties/iterations, (iterations - wins - ties)/iterations


def calculate_pot_odds_math(bet_pct):
    b = bet_pct / 100.0
    equity_to_call = (b / (1.0 + 2.0 * b)) * 100.0
    ratio_first = round((1.0 + b) / b, 1) if b > 0 else 0
    outs_flop = round(equity_to_call / 4.0, 1)
    outs_turn = round(equity_to_call / 2.0, 1)
    return equity_to_call, f"{ratio_first} : 1", outs_flop, outs_turn


# 버튼 및 뱃지 동적 CSS 스타일
dynamic_button_styles = []

# 1) 169 핸드 매트릭스 버튼
cur_h1, cur_h2 = st.session_state.hero_card1, st.session_state.hero_card2
cur_s1 = cur_h1[1] if len(cur_h1) > 1 else "s"
cur_s2 = cur_h2[1] if len(cur_h2) > 1 else "h"

for r1 in RANKS:
    for r2 in RANKS:
        ht = hand_type(r1, r2)
        txt_col, bg_col = get_hand_colors(r1, r2)
        is_selected = (ht == hand_type(cur_h1[0], cur_h2[0]))
        key_id = f"mat_{r1}_{r2}"
        if is_selected:
            btn_bg, btn_txt, btn_border = "#dc2626", "#ffffff", "#f59e0b"
            extra_style = "font-weight: 900 !important; box-shadow: 0 0 8px #f59e0b !important;"
        else:
            btn_bg, btn_txt, btn_border, extra_style = bg_col, txt_col, border_col, ""
        dynamic_button_styles.append(f"""
            div[class*="st-key-{key_id}"] button, div[class*="st-key-{key_id}"] button:hover {{
                background-color: {btn_bg} !important; border: 1px solid {btn_border} !important; {extra_style}
            }}
            div[class*="st-key-{key_id}"] button * {{ color: {btn_txt} !important; font-weight: bold !important; }}
        """)

# 2) 카드 피커 버튼
for r in RANKS:
    for s in SUITS:
        card_code = f"{r}{s}"
        key_id = f"pick_card_{card_code}"
        has_red = s in ["h", "d"]
        bg_c_picker = "#2a1215" if (is_dark and has_red) else ("#1e293b" if is_dark else ("#fef2f2" if has_red else "#ffffff"))
        border_c_picker = "#991b1b" if has_red else ("#475569" if is_dark else "#cbd5e1")
        dynamic_button_styles.append(f"""
            div[class*="st-key-{key_id}"] button, div[class*="st-key-{key_id}"] button:hover {{
                background-color: {bg_c_picker} !important; border: 1px solid {border_c_picker} !important;
            }}
            div[class*="st-key-{key_id}"] button * {{ font-weight: bold !important; font-size: 0.88rem !important; }}
        """)

# 전역 CSS 적용
st.markdown(f"""
    <style>
    .stApp {{ background-color: {app_bg} !important; color: {text_main} !important; }}
    div[data-testid="stHorizontal"] > div {{ padding: 0px 1px !important; }}
    .stButton button {{
        width: 100% !important; padding: 3px 0px !important; font-size: 0.82rem !important; min-height: 36px !important; border-radius: 6px !important;
    }}
    {" ".join(dynamic_button_styles)}
    .tier-badge {{ display: inline-block; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 0.85rem; margin: 0 2px; }}
    .tier-badge-s {{ background-color: {bg_s} !important; color: {badge_txt} !important; }}
    .tier-badge-a {{ background-color: {bg_a} !important; color: {badge_txt} !important; }}
    .tier-badge-b {{ background-color: {bg_b} !important; color: {badge_txt} !important; }}
    .tier-badge-c {{ background-color: {bg_c} !important; color: {badge_txt} !important; }}
    .tier-badge-d {{ background-color: {bg_d} !important; color: {badge_txt} !important; border: 1px solid {border_col} !important; }}

    .card-badge {{ display: inline-block; padding: 4px 10px; font-size: 1.1rem; font-weight: bold; border-radius: 6px; margin: 2px; }}
    .suit-s, .suit-c {{ background-color: #1e293b; color: #ffffff; border: 1px solid #475569; }}
    .suit-h, .suit-d {{ background-color: #450a0a; color: #f87171; border: 1px solid #991b1b; }}
    
    .action-card {{ background-color: {card_bg}; border-radius: 8px; padding: 15px; border: 1px solid {border_col}; text-align: center; margin-top: 10px; }}
    .action-title {{ font-size: 1.5rem; font-weight: bold; }}
    .action-fold {{ color: #f87171; }}
    .action-check {{ color: #38bdf8; }}
    .action-call {{ color: #facc15; }}
    .action-raise {{ color: #4ade80; }}
    .action-allin {{ color: #fb923c; }}
    </style>
""", unsafe_allow_html=True)


# ==========================================
# 4. 탭 구성 (어드바이저 vs 모의게임)
# ==========================================
tab_advisor, tab_game = st.tabs(["📊 실시간 승률 & 수학적 어드바이저", "🎮 모의게임 (홀덤 연습)"])


# ==========================================
# [TAB 1] 실시간 승률 & 수학적 어드바이저 (기존 기능 유지)
# ==========================================
with tab_advisor:
    st.title("♠️ 실시간 홀덤 승률 & 수학적 어드바이저")

    st.markdown(f"""
        <div style="font-size:0.85rem; margin-bottom:8px; color:{text_sub}; font-weight:bold;">
            <b>글씨 색상:</b> <span style="color:{txt_pair};">파랑(페어)</span> | <span style="color:{txt_suited};">초록(수딧)</span> | <span style="color:{txt_off};">주황(오프수딧)</span> &nbsp;&nbsp;|&nbsp;&nbsp; 
            <b>배경 색상:</b> <span class="tier-badge tier-badge-s">S급</span> <span class="tier-badge tier-badge-a">A급</span> <span class="tier-badge tier-badge-b">B급</span> <span class="tier-badge tier-badge-c">C급</span> <span class="tier-badge tier-badge-d">D급</span>
        </div>
    """, unsafe_allow_html=True)

    # 13x13 매트릭스 그리드
    matrix_cols = st.columns([0.6] + [1]*13)
    matrix_cols[0].write("")
    for j, r in enumerate(RANKS): matrix_cols[j+1].markdown(f"**{r}**")
        
    for i, r1 in enumerate(RANKS):
        m_row = st.columns([0.6] + [1]*13)
        m_row[0].markdown(f"**{r1}**")
        for j, r2 in enumerate(RANKS):
            ht = hand_type(r1, r2)
            if m_row[j+1].button(ht, key=f"mat_{r1}_{r2}", use_container_width=True):
                if r1 == r2:
                    st.session_state.hero_card1, st.session_state.hero_card2 = f"{r1}s", f"{r2}h"
                elif RANKS.index(r1) < RANKS.index(r2):
                    st.session_state.hero_card1, st.session_state.hero_card2 = f"{r1}s", f"{r2}s"
                else:
                    st.session_state.hero_card1, st.session_state.hero_card2 = f"{r1}s", f"{r2}h"
                st.rerun()

    st.markdown("---")
    h1, h2 = st.session_state.hero_card1, st.session_state.hero_card2
    r1, r2 = h1[0], h2[0]
    s1, s2 = h1[1], h2[1]
    ht = hand_type(r1, r2)
    hero_cards = [h1, h2]
    h_html = "".join([format_card_html(c) for c in hero_cards])

    st.markdown(f"### 📌 내 핸드: {h_html} `({ht})`", unsafe_allow_html=True)
    st.write("⚡ **무늬(Suit) 원클릭 변경:**")

    if r1 == r2:
        pair_combos = [("s", "h"), ("s", "d"), ("s", "c"), ("h", "d"), ("h", "c"), ("d", "c")]
        p_cols = st.columns(6)
        for idx, (p1, p2) in enumerate(pair_combos):
            btn_label = f"{get_suit_md(p1)}{get_suit_md(p2)} ({format_card_md(r1, p1)} {format_card_md(r2, p2)})"
            if p_cols[idx].button(btn_label, key=f"quick_pair_{p1}_{p2}", use_container_width=True):
                st.session_state.hero_card1, st.session_state.hero_card2 = f"{r1}{p1}", f"{r2}{p2}"
                st.rerun()
    elif s1 == s2:
        s_cols = st.columns(4)
        for idx, suit in enumerate(SUITS):
            btn_label = f"{get_suit_md(suit)}{get_suit_md(suit)} ({format_card_md(r1, suit)} {format_card_md(r2, suit)})"
            if s_cols[idx].button(btn_label, key=f"quick_suited_{suit}", use_container_width=True):
                st.session_state.hero_card1, st.session_state.hero_card2 = f"{r1}{suit}", f"{r2}{suit}"
                st.rerun()
    else:
        off_combos = [("s", "h"), ("s", "d"), ("s", "c"), ("h", "d"), ("h", "c"), ("d", "c")]
        o_cols = st.columns(6)
        for idx, (p1, p2) in enumerate(off_combos):
            btn_label = f"{get_suit_md(p1)}{get_suit_md(p2)} ({format_card_md(r1, p1)} {format_card_md(r2, p2)})"
            if o_cols[idx].button(btn_label, key=f"quick_off_{p1}_{p2}", use_container_width=True):
                st.session_state.hero_card1, st.session_state.hero_card2 = f"{r1}{p1}", f"{r2}{p2}"
                st.rerun()

    # 원클릭 보드 선택
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
        if st.button("🗑️ 보드 카드 전체 초기화", key="reset_board_all"):
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
            if card_code in used_cards:
                suit_row[j+1].markdown("<div style='min-height:36px;'></div>", unsafe_allow_html=True)
            else:
                if suit_row[j+1].button(btn_label, key=f"pick_card_{card_code}", disabled=len(st.session_state.board_cards)>=5, use_container_width=True):
                    if len(st.session_state.board_cards) < 5:
                        st.session_state.board_cards.append(card_code)
                        st.rerun()

    board_cards = st.session_state.board_cards
    b_html = "".join([format_card_html(c) for c in board_cards]) if board_cards else "<span style='color:gray;'>프리플랍 (보드 없음)</span>"
    st.markdown(f"**현재 확정 보드:** {b_html}", unsafe_allow_html=True)

    if len(hero_cards + board_cards) >= 5:
        best_korean_hand = get_best_korean_hand(hero_cards, board_cards)
        st.markdown(f"""
            <div style="background-color:{card_bg}; border:2px solid #3b82f6; border-radius:8px; padding:12px 18px; margin-top:12px; text-align:center;">
                <span style="color:{text_sub}; font-size:0.95rem; font-weight:bold;">🏆 현재 최고 5카드 족보 판정 (7포커 족보 기준):</span>
                <span style="color:#f59e0b; font-size:1.3rem; font-weight:bold; margin-left:12px;">{best_korean_hand}</span>
            </div>
        """, unsafe_allow_html=True)

    # 팟 오즈 계산
    st.markdown("---")
    st.subheader("📊 상대 베팅 크기 & 팟 오즈(Pot Odds) 원클릭 선택")
    preset_cols = st.columns(8)
    presets = [("25% 팟", 25.0), ("33% 팟", 33.3), ("50% 팟", 50.0), ("66% 팟", 66.6), ("75% 팟", 75.0), ("100% (팟)", 100.0), ("150% (오버)", 150.0), ("200% (2배)", 200.0)]
    for idx, (label, val) in enumerate(presets):
        if preset_cols[idx].button(label, key=f"preset_btn_{idx}", use_container_width=True):
            st.session_state.bet_ratio_pct = val
            st.rerun()

    req_eq, pot_ratio_str, outs_req_flop, outs_turn = calculate_pot_odds_math(st.session_state.bet_ratio_pct)

    # 승률 계산 진단 결과
    st.markdown("---")
    st.subheader("🚀 실시간 승률 및 수학적 진단 결과")

    if len(board_cards) not in (0, 3, 4, 5):
        st.warning("⚠️ 보드 카드는 **0장(프리플랍)**, **3장(플랍)**, **4장(턴)**, **5장(리버)** 조합일 때 정확히 계산됩니다.")
    else:
        try:
            hero_treys = [Card.new(c) for c in hero_cards]
            board_treys = [Card.new(c) for c in board_cards]
            equity, win_rate, tie_rate, loss_rate = calculate_monte_carlo_equity(hero_treys, board_treys, opponents_count, sim_iterations)
            eq_pct = equity * 100.0
            ev_diff = eq_pct - req_eq
            
            col_hero_left, col_math_right = st.columns(2)
            with col_hero_left:
                st.markdown(f"""
                    <div style="background-color:{card_bg}; border:2px solid #22c55e; border-radius:10px; padding:16px; text-align:center;">
                        <div style="color:#4ade80; font-size:1.05rem; font-weight:bold;">🎲 내 승률 (모든 경우 반영)</div>
                        <div style="font-size:2.4rem; font-weight:bold; color:{text_main}; margin:8px 0;">{eq_pct:.1f}%</div>
                        <div style="font-size:0.88rem; color:{text_sub}; line-height:1.5;">
                            승리: <b>{win_rate*100:.1f}%</b> | 비김: <b>{tie_rate*100:.1f}%</b> | 패배: <b>{loss_rate*100:.1f}%</b><br>
                            기대값 차이 (EV Diff): <b>{ev_diff:+.1f}%p</b>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

            with col_math_right:
                st.markdown(f"""
                    <div style="background-color:{card_bg}; border:2px solid #3b82f6; border-radius:10px; padding:16px; text-align:center;">
                        <div style="color:#60a5fa; font-size:1.05rem; font-weight:bold;">📐 콜 필요 승률 (참고용)</div>
                        <div style="font-size:2.4rem; font-weight:bold; color:{text_main}; margin:8px 0;">{req_eq:.1f}%</div>
                        <div style="font-size:0.88rem; color:{text_sub}; line-height:1.5;">
                            팟 오즈 비율: <b>{pot_ratio_str}</b><br>
                            필요 아웃츠 (Flop/Turn): <b>약 {outs_req_flop:.0f}개 / {outs_turn:.0f}개</b>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
                
            st.markdown("<br>", unsafe_allow_html=True)

            if eq_pct >= req_eq + 15.0:
                rec_action, action_class = "레이즈 / 올인 (Raise or All-in)", "action-allin"
                math_status = f"🔥 **압도적 +EV 상태 (내 승률 {eq_pct:.1f}% vs 필요 승률 {req_eq:.1f}%)**"
                advice_text = f"내 승률이 콜 필요 승률보다 **+{ev_diff:.1f}%p** 높습니다. 단순히 콜만 하는 것은 손해이며, 레이즈로 팟 크기를 대폭 키워야 합니다."
            elif eq_pct >= req_eq:
                rec_action, action_class = "콜 추천 (Call)", "action-call"
                math_status = f"✅ **양의 기대값(+EV) 콜 구간 (내 승률 {eq_pct:.1f}% vs 필요 승률 {req_eq:.1f}%)**"
                advice_text = f"내 승률이 팟 오즈가 요구하는 최소 승률을 **+{ev_diff:.1f}%p** 웃돌고 있습니다. 콜(Call)이 수학적으로 무조건 유리합니다."
            elif eq_pct >= req_eq - 5.0:
                rec_action, action_class = "콜 또는 폴드 (Marginal Call / Fold)", "action-check"
                math_status = f"⚠️ **경계선 구간 (내 승률 {eq_pct:.1f}% vs 필요 승률 {req_eq:.1f}%)**"
                advice_text = f"승률이 필요 승률에 비해서 **{abs(ev_diff):.1f}%p** 부족합니다. 포지션이나 블러핑 가능성에 따라 콜을 선택할 수 있습니다."
            else:
                rec_action, action_class = "폴드 권장 (Fold)", "action-fold"
                math_status = f"🛑 **음의 기대값(-EV) 손실 구간 (내 승률 {eq_pct:.1f}% vs 필요 승률 {req_eq:.1f}%)**"
                advice_text = f"현재 승률({eq_pct:.1f}%)로는 팟 오즈 필요 승률({req_eq:.1f}%)을 충족하지 못합니다 (**{ev_diff:.1f}%p 부족**). 폴드(Fold)가 상책입니다."

            st.markdown(f"""
                <div class="action-card">
                    <div style="color: {text_sub}; font-size: 0.95rem;">수학적 판정 결과</div>
                    <div class="action-title {action_class}">{rec_action}</div>
                    <div style="margin-top: 8px; font-size: 1.05rem;">{math_status}</div>
                </div>
            """, unsafe_allow_html=True)
            st.info(f"💡 **수학적 가치 진단 상세:**\n\n{advice_text}")

        except Exception as e:
            st.error(f"계산 도중 오류가 발생했습니다: {str(e)}")


# ==========================================
# [TAB 2] 모의게임 (홀덤 연습 모드)
# ==========================================
with tab_game:
    st.title("🎮 1:1 홀덤 모의게임 연습장")
    st.caption("AI 상대와 실전과 동일한 대전을 즐기며 승률과 팟 오즈 판단을 실전 연습해보세요.")

    # 헬퍼 함수: 새 판 시작
    def start_mock_hand():
        deck = [f"{r}{s}" for r in RANKS for s in SUITS]
        random.shuffle(deck)
        st.session_state.mg_hero_cards = [deck.pop(), deck.pop()]
        st.session_state.mg_opp_cards = [deck.pop(), deck.pop()]
        st.session_state.mg_board_cards = []
        st.session_state.mg_deck = deck
        
        # 스몰/빅 블라인드 적용 (SB: 10, BB: 20)
        st.session_state.mg_user_chips -= 10
        st.session_state.mg_opp_chips -= 20
        st.session_state.mg_user_bet = 10
        st.session_state.mg_opp_bet = 20
        st.session_state.mg_pot = 30
        st.session_state.mg_stage = "PREFLOP"
        st.session_state.mg_result_msg = ""
        st.session_state.mg_last_action = "게임 시작 (내 SB 10 / AI BB 20)"

    # 상단 메트릭 대시보드
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    m_col1.metric("👤 내 잔여 칩", f"{st.session_state.mg_user_chips} 칩")
    m_col2.metric("💰 현재 팟 사이즈", f"{st.session_state.mg_pot} 칩")
    m_col3.metric("🤖 AI 상대 칩", f"{st.session_state.mg_opp_chips} 칩")
    m_col4.metric("📌 진행 단계", st.session_state.mg_stage)

    st.markdown("---")

    # 게임 진행 및 액션 화면
    if st.session_state.mg_stage == "IDLE":
        if st.session_state.mg_result_msg:
            st.success(st.session_state.mg_result_msg) if "승리" in st.session_state.mg_result_msg or "획득" in st.session_state.mg_result_msg else st.warning(st.session_state.mg_result_msg)

        if st.session_state.mg_user_chips < 10 or st.session_state.mg_opp_chips < 10:
            st.error("⚠️ 한 쪽의 칩이 부족합니다! 아래 버튼을 눌러 칩을 리셋하세요.")
            if st.button("🔄 칩 1,000개로 리셋 및 다시 시작", type="primary"):
                st.session_state.mg_user_chips = 1000
                st.session_state.mg_opp_chips = 1000
                start_mock_hand()
                st.rerun()
        else:
            if st.button("🃏 새 판 시작하기 (SB 10 / BB 20)", type="primary", use_container_width=True):
                start_mock_hand()
                st.rerun()

    else: # PREFLOP, FLOP, TURN, RIVER
        # AI 포커 테이블 레이아웃
        st.markdown(f"### 🤖 상대방 (AI)")
        if st.session_state.mg_stage == "SHOWDOWN":
            opp_h = "".join([format_card_html(c) for c in st.session_state.mg_opp_cards])
            opp_hand_rank = get_best_korean_hand(st.session_state.mg_opp_cards, st.session_state.mg_board_cards)
            st.markdown(f"**상대 패:** {opp_h} `({opp_hand_rank})`", unsafe_allow_html=True)
        else:
            st.markdown("<span style='font-size:1.5rem;'>🂠 🂠</span> <span style='color:gray;'>(카드 숨김)</span>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### 🃏 커뮤니티 보드")
        if st.session_state.mg_board_cards:
            b_html = "".join([format_card_html(c) for c in st.session_state.mg_board_cards])
            st.markdown(b_html, unsafe_allow_html=True)
        else:
            st.markdown("<span style='color:gray;'>[ 프리플랍 진행 중 - 보드 카드 없음 ]</span>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        hero_h = "".join([format_card_html(c) for c in st.session_state.mg_hero_cards])
        hero_rank_str = ""
        if len(st.session_state.mg_hero_cards + st.session_state.mg_board_cards) >= 5:
            hero_rank_str = f" `({get_best_korean_hand(st.session_state.mg_hero_cards, st.session_state.mg_board_cards)})`"
        st.markdown(f"### 👤 내 핸드: {hero_h}{hero_rank_str}", unsafe_allow_html=True)

        st.info(f"💬 **최근 게임 상황:** {st.session_state.mg_last_action}")

        # 사용자 액션 계산
        call_needed = st.session_state.mg_opp_bet - st.session_state.mg_user_bet
        
        st.markdown("---")
        st.write("⚡ **내 액션 선택:**")
        act_col1, act_col2, act_col3, act_col4 = st.columns(4)

        # 다음 스테이지 이동 헬퍼
        def advance_stage():
            st.session_state.mg_user_bet = 0
            st.session_state.mg_opp_bet = 0
            if st.session_state.mg_stage == "PREFLOP":
                st.session_state.mg_board_cards = [st.session_state.mg_deck.pop() for _ in range(3)]
                st.session_state.mg_stage = "FLOP"
            elif st.session_state.mg_stage == "FLOP":
                st.session_state.mg_board_cards.append(st.session_state.mg_deck.pop())
                st.session_state.mg_stage = "TURN"
            elif st.session_state.mg_stage == "TURN":
                st.session_state.mg_board_cards.append(st.session_state.mg_deck.pop())
                st.session_state.mg_stage = "RIVER"
            elif st.session_state.mg_stage == "RIVER":
                # 쇼다운 판정
                st.session_state.mg_stage = "SHOWDOWN"
                h_treys = [Card.new(c) for c in st.session_state.mg_hero_cards]
                o_treys = [Card.new(c) for c in st.session_state.mg_opp_cards]
                b_treys = [Card.new(c) for c in st.session_state.mg_board_cards]
                
                h_score = EVALUATOR.evaluate(b_treys, h_treys)
                o_score = EVALUATOR.evaluate(b_treys, o_treys)
                
                h_name = get_best_korean_hand(st.session_state.mg_hero_cards, st.session_state.mg_board_cards)
                o_name = get_best_korean_hand(st.session_state.mg_opp_cards, st.session_state.mg_board_cards)
                
                if h_score < o_score:
                    st.session_state.mg_user_chips += st.session_state.mg_pot
                    st.session_state.mg_result_msg = f"🎉 **쇼다운 승리!** 내 패: {h_name} vs 상대 패: {o_name} — **+{st.session_state.mg_pot} 칩** 획득!"
                elif h_score > o_score:
                    st.session_state.mg_opp_chips += st.session_state.mg_pot
                    st.session_state.mg_result_msg = f"😭 **쇼다운 패배!** 내 패: {h_name} vs 상대 패: {o_name} — 상대방이 {st.session_state.mg_pot} 칩 획득"
                else:
                    st.session_state.mg_user_chips += st.session_state.mg_pot // 2
                    st.session_state.mg_opp_chips += st.session_state.mg_pot // 2
                    st.session_state.mg_result_msg = f"🤝 **비김 (Split)!** 내 패: {h_name} vs 상대 패: {o_name} — 팟 반씩 분할"
                st.session_state.mg_stage = "IDLE"

        # AI 의사결정 헬퍼
        def ai_turn():
            # simple AI logic
            ai_rand = random.random()
            if call_needed > 0:
                if ai_rand < 0.7: # 70% 콜
                    st.session_state.mg_opp_chips -= call_needed
                    st.session_state.mg_pot += call_needed
                    st.session_state.mg_opp_bet += call_needed
                    st.session_state.mg_last_action = f"AI가 {call_needed} 칩 콜(Call)을 했습니다."
                    advance_stage()
                else: # 30% 폴드
                    st.session_state.mg_user_chips += st.session_state.mg_pot
                    st.session_state.mg_result_msg = f"🎉 상대방(AI)이 기권(Fold)하여 **+{st.session_state.mg_pot} 칩**을 획득했습니다!"
                    st.session_state.mg_stage = "IDLE"
            else:
                if ai_rand < 0.6: # 체크
                    st.session_state.mg_last_action = "상대방(AI)이 체크(Check)했습니다."
                    advance_stage()
                else: # 30 베팅
                    bet_amt = min(30, st.session_state.mg_opp_chips)
                    st.session_state.mg_opp_chips -= bet_amt
                    st.session_state.mg_pot += bet_amt
                    st.session_state.mg_opp_bet += bet_amt
                    st.session_state.mg_last_action = f"상대방(AI)이 {bet_amt} 칩 베팅/레이즈를 했습니다."

        # 버튼 1: CHECK / CALL
        if call_needed == 0:
            if act_col1.button("✅ 체크 (Check)", use_container_width=True):
                st.session_state.mg_last_action = "내가 체크(Check)했습니다."
                advance_stage()
                st.rerun()
        else:
            if act_col1.button(f"📞 콜 ({call_needed} 칩)", use_container_width=True):
                actual_call = min(call_needed, st.session_state.mg_user_chips)
                st.session_state.mg_user_chips -= actual_call
                st.session_state.mg_pot += actual_call
                st.session_state.mg_user_bet += actual_call
                st.session_state.mg_last_action = f"내가 {actual_call} 칩 콜(Call)했습니다."
                advance_stage()
                st.rerun()

        # 버튼 2 & 3: RAISE
        if act_col2.button("🔺 레이즈 (+30)", use_container_width=True):
            r_amt = call_needed + 30
            actual_r = min(r_amt, st.session_state.mg_user_chips)
            st.session_state.mg_user_chips -= actual_r
            st.session_state.mg_pot += actual_r
            st.session_state.mg_user_bet += actual_r
            st.session_state.mg_last_action = f"내가 {actual_r} 칩으로 레이즈했습니다."
            ai_turn()
            st.rerun()

        if act_col3.button("🔥 올인 (All-In)", use_container_width=True):
            allin_amt = st.session_state.mg_user_chips
            st.session_state.mg_pot += allin_amt
            st.session_state.mg_user_bet += allin_amt
            st.session_state.mg_user_chips = 0
            st.session_state.mg_last_action = "내가 올인(All-In)했습니다!"
            ai_turn()
            st.rerun()

        # 버튼 4: FOLD
        if act_col4.button("🏳️ 폴드 (Fold)", use_container_width=True):
            st.session_state.mg_opp_chips += st.session_state.mg_pot
            st.session_state.mg_result_msg = f"🏳️ 내 기권(Fold)으로 상대방이 {st.session_state.mg_pot} 칩을 가져갔습니다."
            st.session_state.mg_stage = "IDLE"
            st.rerun()
