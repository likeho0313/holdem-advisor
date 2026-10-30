import random
import itertools
from collections import Counter
import streamlit as st
from treys import Card, Deck, Evaluator

# ==========================================
# 0. 페이지 기본 설정 및 초기 세션 상태
# ==========================================
st.set_page_config(
    page_title="텍사스 홀덤 실시간 승률 & 토너먼트 모의게임 어드바이저",
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

# --- [어드바이저 세션 상태] ---
if "hero_card1" not in st.session_state:
    st.session_state.hero_card1 = "As"
if "hero_card2" not in st.session_state:
    st.session_state.hero_card2 = "Ks"
if "board_cards" not in st.session_state:
    st.session_state.board_cards = []
if "bet_ratio_pct" not in st.session_state:
    st.session_state.bet_ratio_pct = 25.0

# --- [모의게임 세션 상태] ---
if "mg_stage" not in st.session_state:
    st.session_state.mg_stage = "IDLE"  # IDLE, PREFLOP, FLOP, TURN, RIVER, SHOWDOWN
if "mg_user_chips" not in st.session_state:
    st.session_state.mg_user_chips = 2000
if "mg_user_rebuys" not in st.session_state:
    st.session_state.mg_user_rebuys = 3
if "mg_opp_chips" not in st.session_state:
    st.session_state.mg_opp_chips = []
if "mg_opp_rebuys" not in st.session_state:
    st.session_state.mg_opp_rebuys = []
if "mg_opp_eliminated" not in st.session_state:
    st.session_state.mg_opp_eliminated = []
if "mg_user_eliminated" not in st.session_state:
    st.session_state.mg_user_eliminated = False

if "mg_pot" not in st.session_state:
    st.session_state.mg_pot = 0
if "mg_dealer_pos" not in st.session_state:
    st.session_state.mg_dealer_pos = 0  # 0: Hero, 1..N: AI들
if "mg_active_turn" not in st.session_state:
    st.session_state.mg_active_turn = 0
if "mg_acted_players" not in st.session_state:
    st.session_state.mg_acted_players = []

if "mg_user_total_contrib" not in st.session_state:
    st.session_state.mg_user_total_contrib = 0
if "mg_opp_total_contribs" not in st.session_state:
    st.session_state.mg_opp_total_contribs = []

if "mg_hero_cards" not in st.session_state:
    st.session_state.mg_hero_cards = []
if "mg_opp_cards_list" not in st.session_state:
    st.session_state.mg_opp_cards_list = []
if "mg_opp_folded" not in st.session_state:
    st.session_state.mg_opp_folded = []
if "mg_user_folded" not in st.session_state:
    st.session_state.mg_user_folded = False
if "mg_board_cards" not in st.session_state:
    st.session_state.mg_board_cards = []
if "mg_deck" not in st.session_state:
    st.session_state.mg_deck = []
if "mg_user_bet" not in st.session_state:
    st.session_state.mg_user_bet = 0
if "mg_opp_bets" not in st.session_state:
    st.session_state.mg_opp_bets = []
if "mg_current_max_bet" not in st.session_state:
    st.session_state.mg_current_max_bet = 0
if "mg_result_msg" not in st.session_state:
    st.session_state.mg_result_msg = ""
if "mg_pot_details_rows" not in st.session_state:
    st.session_state.mg_pot_details_rows = []
if "mg_payouts" not in st.session_state:
    st.session_state.mg_payouts = []
if "mg_all_contribs" not in st.session_state:
    st.session_state.mg_all_contribs = []
if "mg_player_histories" not in st.session_state:
    st.session_state.mg_player_histories = {}
if "mg_showdown_done" not in st.session_state:
    st.session_state.mg_showdown_done = False


# ==========================================
# 1. 169 핸드 명시적 티어(S, A, B, C, D) 정의
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
# 2. 사이드바 설정
# ==========================================
st.sidebar.title("⚙️ 게임 설정 & UI 테마")

opponents_count = st.sidebar.slider("상대 플레이어 수 (1~9명)", min_value=1, max_value=9, value=3)

start_chips_setting = st.sidebar.slider(
    "시작 칩 (Start Chips)",
    min_value=100,
    max_value=10000,
    value=2000,
    step=100
)

rebuy_setting = st.sidebar.slider(
    "최대 리바이 (Re-buy) 가능 횟수",
    min_value=0,
    max_value=5,
    value=3,
    step=1
)

bb_setting = st.sidebar.slider(
    "빅 블라인드 (BB) 금액",
    min_value=10,
    max_value=500,
    value=20,
    step=10
)
sb_setting = bb_setting // 2

sim_iterations = st.sidebar.select_slider("승률 정밀도 (시뮬레이션)", options=[1000, 2500, 5000], value=2500)

st.sidebar.markdown("---")
theme_mode = st.sidebar.radio("🎨 UI 테마 선택", ["☀️ 라이트 모드", "🌙 다크 모드"], index=0)
is_dark = (theme_mode == "🌙 다크 모드")

with st.sidebar.expander("📖 서비스 사용 설명서", expanded=True):
    st.markdown(f"""
    **📊 실시간 승률 어드바이저 탭**
    1. 169 매트릭스에서 내 핸드와 무늬 조합을 고릅니다.
    2. 커뮤니티 보드(플랍/턴/리버) 카드를 선택합니다.
    3. '내 승률'과 '콜 필요 승률'을 실시간 비교하여 +EV 의사결정을 내립니다.

    **🎮 1:N 토너먼트 모의게임 탭**
    1. **올인 시 수동 오픈**: 올인 상태가 되어도 카드 한 장씩 수동 오픈하여 손끝 쫄깃함을 유지합니다.
    2. **베팅액 명확화**: 현재 라운드 베팅액과 이번 핸드 누적 베팅액이 완벽히 구분되어 표기됩니다.
    3. **상세한 손익 리포트**: 최종 수령 및 손익 차액을 계산해 보여줍니다.
    """)


# ==========================================
# 3. 테마 및 공통 헬퍼 함수
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
    if i1 == i2: return r1 + r2
    elif i1 < i2: return r1 + r2 + "s"
    else: return r2 + r1 + "o"


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
    if not card_code or len(card_code) < 2: return ""
    rank = card_code[0].replace("T", "10")
    suit = card_code[1]
    symbol = SUIT_SYMBOLS.get(suit, "")
    css_class = f"suit-{suit}"
    return f'<span class="card-badge {css_class}">{rank}{symbol}</span>'


def format_action_chip_html(action_type, text_detail):
    chip_class_map = {
        "SB": "chip-sb", "BB": "chip-bb", "CALL": "chip-call",
        "CHECK": "chip-check", "RAISE": "chip-raise", "BET": "chip-raise", "FOLD": "chip-fold"
    }
    icon_map = {
        "SB": "🟡", "BB": "🟠", "CALL": "🟢", "CHECK": "🔵", "RAISE": "🔴", "BET": "🔴", "FOLD": "⚪"
    }
    css_cls = chip_class_map.get(action_type, "chip-check")
    icon = icon_map.get(action_type, "🪙")
    return f'<span class="poker-chip {css_cls}">{icon} {text_detail}</span>'


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


# 동적 CSS 주입
dynamic_button_styles = []
cur_h1, cur_h2 = st.session_state.hero_card1, st.session_state.hero_card2

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
    
    .poker-chip {{
        display: inline-flex;
        align-items: center;
        gap: 3px;
        padding: 2px 7px;
        border-radius: 12px;
        font-weight: bold;
        font-size: 0.76rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.3);
        margin: 1px 2px;
        white-space: nowrap;
    }}
    .chip-sb {{ background-color: #fef08a; color: #854d0e; border: 1px solid #eab308; }}
    .chip-bb {{ background-color: #fed7aa; color: #9a3412; border: 1px solid #f97316; }}
    .chip-call {{ background-color: #bbf7d0; color: #166534; border: 1px solid #22c55e; }}
    .chip-check {{ background-color: #e0f2fe; color: #075985; border: 1px solid #38bdf8; }}
    .chip-raise {{ background-color: #fecaca; color: #991b1b; border: 1px solid #ef4444; font-weight: 900; }}
    .chip-fold {{ background-color: #f1f5f9; color: #64748b; border: 1px solid #94a3b8; }}

    .player-action-box {{
        background-color: {card_bg};
        border: 1px solid {border_col};
        border-radius: 6px;
        padding: 6px 8px;
        font-size: 0.78rem;
        margin-top: 6px;
        line-height: 1.4;
        min-height: 48px;
    }}
    </style>
""", unsafe_allow_html=True)


# ==========================================
# 4. 탭 구성
# ==========================================
tab_advisor, tab_game = st.tabs(["📊 실시간 승률 & 수학적 어드바이저", "🎮 1:N 토너먼트 모의게임"])


# ==========================================
# [TAB 1] 실시간 승률 & 수학적 어드바이저
# ==========================================
with tab_advisor:
    st.title("♠️ 실시간 홀덤 승률 & 수학적 어드바이저")

    st.markdown(f"""
        <div style="font-size:0.85rem; margin-bottom:8px; color:{text_sub}; font-weight:bold;">
            <b>글씨 색상:</b> <span style="color:{txt_pair};">파랑(페어)</span> | <span style="color:{txt_suited};">초록(수딧)</span> | <span style="color:{txt_off};">주황(오프수딧)</span> &nbsp;&nbsp;|&nbsp;&nbsp; 
            <b>배경 색상:</b> <span class="tier-badge tier-badge-s">S급</span> <span class="tier-badge tier-badge-a">A급</span> <span class="tier-badge tier-badge-b">B급</span> <span class="tier-badge tier-badge-c">C급</span> <span class="tier-badge tier-badge-d">D급</span>
        </div>
    """, unsafe_allow_html=True)

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
    st.write("⚡ **무늬(Suit) 원클릭 변경 (페어 6콤보 / 수딧 4콤보 / 오프수딧 12콤보):**")

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
        off_combos_12 = [
            ("s", "h"), ("s", "d"), ("s", "c"), ("h", "s"), ("h", "d"), ("h", "c"),
            ("d", "s"), ("d", "h"), ("d", "c"), ("c", "s"), ("c", "h"), ("c", "d")
        ]
        
        o_cols1 = st.columns(6)
        for idx in range(6):
            p1, p2 = off_combos_12[idx]
            btn_label = f"{get_suit_md(p1)}{get_suit_md(p2)} ({format_card_md(r1, p1)} {format_card_md(r2, p2)})"
            if o_cols1[idx].button(btn_label, key=f"quick_off_{p1}_{p2}", use_container_width=True):
                st.session_state.hero_card1, st.session_state.hero_card2 = f"{r1}{p1}", f"{r2}{p2}"
                st.rerun()

        o_cols2 = st.columns(6)
        for idx in range(6, 12):
            p1, p2 = off_combos_12[idx]
            btn_label = f"{get_suit_md(p1)}{get_suit_md(p2)} ({format_card_md(r1, p1)} {format_card_md(r2, p2)})"
            if o_cols2[idx-6].button(btn_label, key=f"quick_off_{p1}_{p2}", use_container_width=True):
                st.session_state.hero_card1, st.session_state.hero_card2 = f"{r1}{p1}", f"{r2}{p2}"
                st.rerun()

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

    st.markdown("---")
    st.subheader("📊 상대 베팅 크기 & 팟 오즈(Pot Odds) 원클릭 선택")
    preset_cols = st.columns(8)
    presets = [("25% 팟", 25.0), ("33% 팟", 33.3), ("50% 팟", 50.0), ("66% 팟", 66.6), ("75% 팟", 75.0), ("100% (팟)", 100.0), ("150% (오버)", 150.0), ("200% (2배)", 200.0)]
    for idx, (label, val) in enumerate(presets):
        if preset_cols[idx].button(label, key=f"preset_btn_{idx}", use_container_width=True):
            st.session_state.bet_ratio_pct = val
            st.rerun()

    req_eq, pot_ratio_str, outs_req_flop, outs_turn = calculate_pot_odds_math(st.session_state.bet_ratio_pct)

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
                        <div style="color:#4ade80; font-size:1.05rem; font-weight:bold;">🎲 내 승률 (상대 {opponents_count}명 반영)</div>
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
# [TAB 2] 1:N 토너먼트 모의게임
# ==========================================
with tab_game:
    total_players = opponents_count + 1

    # -----------------------------------------------------------------
    # 탈락자 및 게임 상태 판단용 헬퍼 함수
    # -----------------------------------------------------------------
    def is_player_eliminated(p_idx):
        if p_idx == 0:
            return st.session_state.mg_user_eliminated
        else:
            ai_i = p_idx - 1
            if ai_i < len(st.session_state.mg_opp_eliminated):
                return st.session_state.mg_opp_eliminated[ai_i]
            return True

    def is_player_folded(p_idx):
        if p_idx == 0:
            return st.session_state.mg_user_folded or st.session_state.mg_user_eliminated
        else:
            ai_i = p_idx - 1
            if ai_i < len(st.session_state.mg_opp_folded):
                return st.session_state.mg_opp_folded[ai_i] or st.session_state.mg_opp_eliminated[ai_i]
            return True

    def get_player_chips(p_idx):
        if p_idx == 0:
            return st.session_state.mg_user_chips
        else:
            ai_i = p_idx - 1
            if ai_i < len(st.session_state.mg_opp_chips):
                return st.session_state.mg_opp_chips[ai_i]
            return 0

    def get_player_name(p_idx):
        if p_idx == 0:
            return "Hero"
        return f"AI {p_idx}"

    def get_active_player_indices():
        """탈락하지 않고 현재 토너먼트에 생존해 있는 플레이어 인덱스 리스트"""
        active = []
        if not st.session_state.mg_user_eliminated:
            active.append(0)
        for i in range(opponents_count):
            if i < len(st.session_state.mg_opp_eliminated) and not st.session_state.mg_opp_eliminated[i]:
                active.append(i + 1)
        return active

    def get_next_turn(current_turn):
        """탈락하지 않은 다음 플레이어로 턴을 넘김"""
        for step in range(1, total_players + 1):
            nxt = (current_turn + step) % total_players
            if not is_player_eliminated(nxt):
                return nxt
        return current_turn

    def get_positions(dealer_pos, active_indices):
        """생존자 수에 맞춘 딜러, SB, BB, UTG 위치 계산 (2명일 때 헤즈업 룰 적용)"""
        num_active = len(active_indices)
        if num_active < 2:
            return 0, 0, 0
        
        if dealer_pos in active_indices:
            d_idx = active_indices.index(dealer_pos)
        else:
            valid = [i for i, p in enumerate(active_indices) if p >= dealer_pos]
            d_idx = valid[0] if valid else 0

        if num_active == 2:
            # 2명 헤즈업(Heads-Up) 특수 규칙: Dealer = SB, 상대 = BB
            sb_pos = active_indices[d_idx]
            bb_pos = active_indices[(d_idx + 1) % 2]
            utg_pos = sb_pos  # 프리플랍 선행동은 SB
            return sb_pos, bb_pos, utg_pos
        else:
            sb_pos = active_indices[(d_idx + 1) % num_active]
            bb_pos = active_indices[(d_idx + 2) % num_active]
            utg_pos = active_indices[(d_idx + 3) % num_active]
            return sb_pos, bb_pos, utg_pos

    def add_player_action(player_name, action_type, detail_str):
        if player_name in st.session_state.mg_player_histories:
            chip_html = format_action_chip_html(action_type, detail_str)
            st.session_state.mg_player_histories[player_name].append(chip_html)

    def reset_entire_tournament():
        st.session_state.mg_user_chips = start_chips_setting
        st.session_state.mg_user_rebuys = rebuy_setting
        st.session_state.mg_user_eliminated = False
        
        st.session_state.mg_opp_chips = [start_chips_setting] * opponents_count
        st.session_state.mg_opp_rebuys = [rebuy_setting] * opponents_count
        st.session_state.mg_opp_eliminated = [False] * opponents_count
        st.session_state.mg_opp_bets = [0] * opponents_count
        st.session_state.mg_opp_total_contribs = [0] * opponents_count
        st.session_state.mg_opp_cards_list = [[] for _ in range(opponents_count)]
        st.session_state.mg_opp_folded = [False] * opponents_count
        
        st.session_state.mg_stage = "IDLE"
        st.session_state.mg_result_msg = ""
        st.session_state.mg_pot_details_rows = []
        st.session_state.mg_payouts = []
        st.session_state.mg_all_contribs = []
        st.session_state.mg_dealer_pos = 0
        st.session_state.mg_showdown_done = False
        st.session_state.mg_user_total_contrib = 0
        st.session_state.mg_hero_cards = []
        st.session_state.mg_board_cards = []
        st.session_state.mg_user_bet = 0
        st.session_state.mg_current_max_bet = 0
        st.session_state.mg_active_turn = 0
        st.session_state.mg_acted_players = []
        st.session_state.mg_user_folded = False

        st.session_state.mg_player_histories = {"Hero": []}
        for i in range(opponents_count):
            st.session_state.mg_player_histories[f"AI {i+1}"] = []

    def resolve_showdown_with_side_pots():
        st.session_state.mg_stage = "SHOWDOWN"
        st.session_state.mg_showdown_done = True
        b_treys = [Card.new(c) for c in st.session_state.mg_board_cards]

        all_contribs = [st.session_state.mg_user_total_contrib] + [
            st.session_state.mg_opp_total_contribs[i] if i < len(st.session_state.mg_opp_total_contribs) else 0 
            for i in range(opponents_count)
        ]
        st.session_state.mg_all_contribs = all_contribs
        all_folded = [is_player_folded(i) for i in range(total_players)]
        
        scores = {}
        hand_descs = {}
        
        if not all_folded[0]:
            h_treys = [Card.new(c) for c in st.session_state.mg_hero_cards]
            scores[0] = EVALUATOR.evaluate(b_treys, h_treys)
            hand_descs[0] = get_best_korean_hand(st.session_state.mg_hero_cards, st.session_state.mg_board_cards)
        
        for idx in range(opponents_count):
            p_id = idx + 1
            if not all_folded[p_id]:
                opp_cards = st.session_state.mg_opp_cards_list[idx] if idx < len(st.session_state.mg_opp_cards_list) else []
                o_treys = [Card.new(c) for c in opp_cards]
                scores[p_id] = EVALUATOR.evaluate(b_treys, o_treys)
                hand_descs[p_id] = get_best_korean_hand(opp_cards, st.session_state.mg_board_cards)

        active_caps = sorted(list(set([all_contribs[i] for i in range(total_players) if not all_folded[i] and all_contribs[i] > 0])))
        if not active_caps:
            active_caps = sorted(list(set([c for c in all_contribs if c > 0])))

        payouts = [0] * total_players
        prev_cap = 0
        pot_rows = []

        for cap_idx, cap in enumerate(active_caps):
            slice_pot = 0
            for i in range(total_players):
                contrib_to_slice = max(0, min(all_contribs[i], cap) - prev_cap)
                slice_pot += contrib_to_slice
            prev_cap = cap

            if slice_pot <= 0:
                continue

            eligible_players = [i for i in range(total_players) if all_contribs[i] >= cap and not all_folded[i]]
            if not eligible_players:
                eligible_players = [i for i in range(total_players) if not all_folded[i]]

            if eligible_players:
                best_score = min([scores[i] for i in eligible_players])
                winners = [i for i in eligible_players if scores[i] == best_score]
                split_amt = slice_pot // len(winners)
                for w in winners:
                    payouts[w] += split_amt
                
                pot_label = "🥇 메인 팟" if cap_idx == 0 else f"🪙 사이드 팟 {cap_idx}"
                eligible_names = ", ".join([get_player_name(p) for p in eligible_players])
                winner_info = ", ".join([f"{get_player_name(w)} (+{split_amt} 칩)" for w in winners])
                winner_hands = " / ".join([hand_descs[w] for w in winners])
                
                pot_rows.append({
                    "label": pot_label,
                    "pot_amt": slice_pot,
                    "cap_amt": cap,
                    "eligible": eligible_names,
                    "winners": winner_info,
                    "hands": winner_hands
                })

        st.session_state.mg_user_chips += payouts[0]
        for idx in range(opponents_count):
            if idx < len(st.session_state.mg_opp_chips):
                st.session_state.mg_opp_chips[idx] += payouts[idx+1]

        st.session_state.mg_pot_details_rows = pot_rows
        st.session_state.mg_payouts = payouts
        st.session_state.mg_result_msg = "🏆 **핸드 쇼다운이 완료되었습니다. 아래 팟 분배 상세표를 확인하세요.**"
        st.session_state.mg_stage = "IDLE"

    def advance_poker_street():
        st.session_state.mg_user_bet = 0
        st.session_state.mg_opp_bets = [0] * opponents_count
        st.session_state.mg_current_max_bet = 0
        st.session_state.mg_acted_players = []
        
        active_idxs = get_active_player_indices()
        if len(active_idxs) == 2:
            sb_p, bb_p, _ = get_positions(st.session_state.mg_dealer_pos, active_idxs)
            next_start_pos = bb_p  # 헤즈업: 플랍 이후는 BB가 먼저 행동
        else:
            sb_p, _, _ = get_positions(st.session_state.mg_dealer_pos, active_idxs)
            next_start_pos = sb_p  # 멀티웨이: 플랍 이후는 SB가 먼저 행동

        st.session_state.mg_active_turn = next_start_pos

        # 더 이상 추가 베팅이 불가능한지 검사 (올인 상황)
        bettable = [i for i in range(total_players) if not is_player_eliminated(i) and not is_player_folded(i) and get_player_chips(i) > 0]
        no_more_betting = (len(bettable) <= 1)

        if st.session_state.mg_stage == "PREFLOP":
            st.session_state.mg_board_cards = [st.session_state.mg_deck.pop() for _ in range(3)]
            st.session_state.mg_stage = "FLOP"
            if not no_more_betting:
                run_poker_turn_engine()
        elif st.session_state.mg_stage == "FLOP":
            st.session_state.mg_board_cards.append(st.session_state.mg_deck.pop())
            st.session_state.mg_stage = "TURN"
            if not no_more_betting:
                run_poker_turn_engine()
        elif st.session_state.mg_stage == "TURN":
            st.session_state.mg_board_cards.append(st.session_state.mg_deck.pop())
            st.session_state.mg_stage = "RIVER"
            if not no_more_betting:
                run_poker_turn_engine()
        elif st.session_state.mg_stage == "RIVER":
            resolve_showdown_with_side_pots()

    def run_poker_turn_engine():
        max_loop_guard = 50
        loop_cnt = 0

        while loop_cnt < max_loop_guard:
            loop_cnt += 1
            curr_p = st.session_state.mg_active_turn

            active_opps = sum(
                1 for i in range(opponents_count) 
                if not is_player_eliminated(i + 1) and not is_player_folded(i + 1)
            )
            hero_act = not is_player_eliminated(0) and not is_player_folded(0)

            # 최후의 1인만 남고 모두 폴드한 경우
            if (active_opps + (1 if hero_act else 0)) <= 1:
                all_contribs = [st.session_state.mg_user_total_contrib] + [
                    st.session_state.mg_opp_total_contribs[i] if i < len(st.session_state.mg_opp_total_contribs) else 0 
                    for i in range(opponents_count)
                ]
                st.session_state.mg_all_contribs = all_contribs
                payouts = [0] * total_players

                if hero_act:
                    payouts[0] = st.session_state.mg_pot
                    st.session_state.mg_payouts = payouts
                    st.session_state.mg_user_chips += st.session_state.mg_pot
                    st.session_state.mg_result_msg = f"🎉 모든 상대가 기권하여 **Hero**가 팟 **+{st.session_state.mg_pot} 칩**을 획득했습니다!"
                    st.session_state.mg_pot_details_rows = []
                else:
                    win_ai = next(
                        (i for i in range(opponents_count) if not is_player_eliminated(i + 1) and not is_player_folded(i + 1)), 
                        0
                    )
                    payouts[win_ai + 1] = st.session_state.mg_pot
                    st.session_state.mg_payouts = payouts
                    if win_ai < len(st.session_state.mg_opp_chips):
                        st.session_state.mg_opp_chips[win_ai] += st.session_state.mg_pot
                    st.session_state.mg_result_msg = f"😭 모든 플레이어가 기권하여 **AI {win_ai+1}**가 팟 **+{st.session_state.mg_pot} 칩**을 획득했습니다!"
                    st.session_state.mg_pot_details_rows = []
                st.session_state.mg_stage = "IDLE"
                break

            # 이번 베팅 라운드 종료 검사
            round_done = True
            for i in range(total_players):
                if is_player_eliminated(i) or is_player_folded(i) or get_player_chips(i) == 0:
                    continue
                
                p_bet = st.session_state.mg_user_bet if i == 0 else st.session_state.mg_opp_bets[i - 1]
                if i not in st.session_state.mg_acted_players or p_bet < st.session_state.mg_current_max_bet:
                    round_done = False
                    break

            if round_done:
                advance_poker_street()
                break

            # 현재 턴이 탈락/폴드/올인 자인 경우 스킵
            if is_player_eliminated(curr_p) or is_player_folded(curr_p) or get_player_chips(curr_p) == 0:
                if curr_p not in st.session_state.mg_acted_players:
                    st.session_state.mg_acted_players.append(curr_p)
                st.session_state.mg_active_turn = get_next_turn(curr_p)
                continue

            # Hero 턴 대기
            if curr_p == 0:
                break

            # AI 턴 액션 처리
            ai_i = curr_p - 1
            ai_chips = st.session_state.mg_opp_chips[ai_i]
            ai_bet = st.session_state.mg_opp_bets[ai_i]
            ai_diff = st.session_state.mg_current_max_bet - ai_bet
            rnd = random.random()

            if ai_diff > 0:
                if rnd < 0.18 and ai_chips > ai_diff + bb_setting:
                    raise_amt = min(ai_diff + bb_setting, ai_chips)
                    st.session_state.mg_opp_chips[ai_i] -= raise_amt
                    st.session_state.mg_opp_bets[ai_i] += raise_amt
                    st.session_state.mg_opp_total_contribs[ai_i] += raise_amt
                    st.session_state.mg_pot += raise_amt
                    st.session_state.mg_current_max_bet = max(st.session_state.mg_current_max_bet, st.session_state.mg_opp_bets[ai_i])
                    
                    is_allin = (st.session_state.mg_opp_chips[ai_i] == 0)
                    act_text = f"Raise +{raise_amt} (ALL IN)" if is_allin else f"Raise +{raise_amt}"
                    add_player_action(f"AI {ai_i+1}", "RAISE", act_text)
                    st.session_state.mg_acted_players = [curr_p]
                elif rnd < 0.32:
                    st.session_state.mg_opp_folded[ai_i] = True
                    add_player_action(f"AI {ai_i+1}", "FOLD", "Fold")
                    st.session_state.mg_acted_players.append(curr_p)
                else:
                    actual_call = min(ai_diff, ai_chips)
                    st.session_state.mg_opp_chips[ai_i] -= actual_call
                    st.session_state.mg_opp_bets[ai_i] += actual_call
                    st.session_state.mg_opp_total_contribs[ai_i] += actual_call
                    st.session_state.mg_pot += actual_call
                    
                    is_allin = (st.session_state.mg_opp_chips[ai_i] == 0)
                    act_text = f"Call {actual_call} (ALL IN)" if is_allin else f"Call {actual_call}"
                    add_player_action(f"AI {ai_i+1}", "CALL", act_text)
                    st.session_state.mg_acted_players.append(curr_p)
            else:
                if rnd < 0.15 and ai_chips >= bb_setting:
                    raise_amt = min(bb_setting, ai_chips)
                    st.session_state.mg_opp_chips[ai_i] -= raise_amt
                    st.session_state.mg_opp_bets[ai_i] += raise_amt
                    st.session_state.mg_opp_total_contribs[ai_i] += raise_amt
                    st.session_state.mg_pot += raise_amt
                    st.session_state.mg_current_max_bet = max(st.session_state.mg_current_max_bet, st.session_state.mg_opp_bets[ai_i])
                    
                    is_allin = (st.session_state.mg_opp_chips[ai_i] == 0)
                    act_text = f"Bet {raise_amt} (ALL IN)" if is_allin else f"Bet {raise_amt}"
                    add_player_action(f"AI {ai_i+1}", "BET", act_text)
                    st.session_state.mg_acted_players = [curr_p]
                else:
                    add_player_action(f"AI {ai_i+1}", "CHECK", "Check")
                    st.session_state.mg_acted_players.append(curr_p)

            st.session_state.mg_active_turn = get_next_turn(curr_p)

    def start_new_hand():
        active_idxs = get_active_player_indices()
        
        # 유저 리바이 검사
        if st.session_state.mg_user_chips <= 0 and st.session_state.mg_user_rebuys <= 0:
            st.session_state.mg_user_eliminated = True

        # AI 리바이 검사
        for idx in range(opponents_count):
            if idx < len(st.session_state.mg_opp_chips):
                if st.session_state.mg_opp_chips[idx] <= 0 and st.session_state.mg_opp_rebuys[idx] > 0:
                    st.session_state.mg_opp_chips[idx] = start_chips_setting
                    st.session_state.mg_opp_rebuys[idx] -= 1
                elif st.session_state.mg_opp_chips[idx] <= 0 and st.session_state.mg_opp_rebuys[idx] == 0:
                    st.session_state.mg_opp_eliminated[idx] = True

        deck = [f"{r}{s}" for r in RANKS for s in SUITS]
        random.shuffle(deck)
        
        if not st.session_state.mg_user_eliminated:
            st.session_state.mg_hero_cards = [deck.pop(), deck.pop()]
            st.session_state.mg_user_folded = False
        else:
            st.session_state.mg_hero_cards = []
            st.session_state.mg_user_folded = True

        st.session_state.mg_opp_cards_list = [[deck.pop(), deck.pop()] for _ in range(opponents_count)]
        st.session_state.mg_opp_folded = [is_player_eliminated(i+1) for i in range(opponents_count)]
        st.session_state.mg_board_cards = []
        st.session_state.mg_deck = deck
        st.session_state.mg_showdown_done = False
        
        st.session_state.mg_user_total_contrib = 0
        st.session_state.mg_opp_total_contribs = [0] * opponents_count
        
        st.session_state.mg_player_histories = {"Hero": []}
        for i in range(opponents_count):
            st.session_state.mg_player_histories[f"AI {i+1}"] = []
        
        # 딜러 버튼 생존자 위치 이동
        active_idxs = get_active_player_indices()
        if active_idxs:
            if st.session_state.mg_dealer_pos in active_idxs:
                cur_d_i = active_idxs.index(st.session_state.mg_dealer_pos)
                st.session_state.mg_dealer_pos = active_idxs[(cur_d_i + 1) % len(active_idxs)]
            else:
                st.session_state.mg_dealer_pos = active_idxs[0]

        sb_pos, bb_pos, utg_pos = get_positions(st.session_state.mg_dealer_pos, active_idxs)

        st.session_state.mg_pot = 0
        st.session_state.mg_user_bet = 0
        st.session_state.mg_opp_bets = [0] * opponents_count

        # SB 지불
        if sb_pos == 0:
            if not st.session_state.mg_user_eliminated:
                val = min(sb_setting, st.session_state.mg_user_chips)
                st.session_state.mg_user_chips -= val
                st.session_state.mg_user_bet = val
                st.session_state.mg_user_total_contrib += val
                st.session_state.mg_pot += val
                add_player_action("Hero", "SB", f"SB {val}")
        else:
            ai_idx = sb_pos - 1
            if not is_player_eliminated(sb_pos):
                val = min(sb_setting, st.session_state.mg_opp_chips[ai_idx])
                st.session_state.mg_opp_chips[ai_idx] -= val
                st.session_state.mg_opp_bets[ai_idx] = val
                st.session_state.mg_opp_total_contribs[ai_idx] += val
                st.session_state.mg_pot += val
                add_player_action(f"AI {ai_idx+1}", "SB", f"SB {val}")

        # BB 지불
        if bb_pos == 0:
            if not st.session_state.mg_user_eliminated:
                val = min(bb_setting, st.session_state.mg_user_chips)
                st.session_state.mg_user_chips -= val
                st.session_state.mg_user_bet = val
                st.session_state.mg_user_total_contrib += val
                st.session_state.mg_pot += val
                add_player_action("Hero", "BB", f"BB {val}")
        else:
            ai_idx = bb_pos - 1
            if not is_player_eliminated(bb_pos):
                val = min(bb_setting, st.session_state.mg_opp_chips[ai_idx])
                st.session_state.mg_opp_chips[ai_idx] -= val
                st.session_state.mg_opp_bets[ai_idx] = val
                st.session_state.mg_opp_total_contribs[ai_idx] += val
                st.session_state.mg_pot += val
                add_player_action(f"AI {ai_idx+1}", "BB", f"BB {val}")

        st.session_state.mg_current_max_bet = bb_setting
        st.session_state.mg_stage = "PREFLOP"
        st.session_state.mg_result_msg = ""
        st.session_state.mg_pot_details_rows = []
        st.session_state.mg_payouts = []
        st.session_state.mg_all_contribs = []
        st.session_state.mg_acted_players = []
        st.session_state.mg_active_turn = utg_pos

        run_poker_turn_engine()

    # -----------------------------------------------------------------
    # 안전 재초기화 검사
    # -----------------------------------------------------------------
    need_reset = (
        "mg_opp_chips" not in st.session_state or
        len(st.session_state.mg_opp_chips) != opponents_count or
        len(st.session_state.mg_opp_bets) != opponents_count or
        len(st.session_state.mg_opp_cards_list) != opponents_count or
        len(st.session_state.mg_opp_folded) != opponents_count or
        len(st.session_state.mg_opp_total_contribs) != opponents_count or
        len(st.session_state.mg_opp_rebuys) != opponents_count or
        len(st.session_state.mg_opp_eliminated) != opponents_count
    )

    if need_reset:
        reset_entire_tournament()

    # -----------------------------------------------------------------
    # UI 메인 출력부
    # -----------------------------------------------------------------
    st.title("🎮 1:N 토너먼트 모의게임")

    active_indices = get_active_player_indices()
    active_players_count = len(active_indices)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("👤 내 칩 (남은 리바이)", f"{st.session_state.mg_user_chips} 칩", f"{st.session_state.mg_user_rebuys}회 가능")
    m2.metric("💰 팟 사이즈", f"{st.session_state.mg_pot} 칩")
    m3.metric("🏆 토너먼트 생존 인원", f"{active_players_count} / {total_players} 명")
    m4.metric("📌 진행 단계", st.session_state.mg_stage)

    st.markdown("---")

    # 결과 안내 및 배너
    if st.session_state.mg_result_msg:
        st.markdown("### 🏆 핸드 결과 안내")
        if "Hero" in st.session_state.mg_result_msg or "획득" in st.session_state.mg_result_msg:
            st.success(st.session_state.mg_result_msg)
        else:
            st.info(st.session_state.mg_result_msg)

    # 사이드 팟 분배 상세 표
    if st.session_state.get("mg_pot_details_rows"):
        st.markdown("#### 📊 메인 팟 / 사이드 팟 분배 상세")
        
        table_md = "| 팟 구분 | 팟 금액 | 팟 기여 상한 | 👥 참여 자격자 | 🏆 승자 (수령액) | 🃏 승리 족보 |\n"
        table_md += "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
        for row in st.session_state.mg_pot_details_rows:
            table_md += f"| **{row['label']}** | **{row['pot_amt']} 칩** | 인당 최대 {row['cap_amt']} 칩 | {row['eligible']} | **{row['winners']}** | {row['hands']} |\n"
        
        st.markdown(table_md)

    # 최종 칩 수령 및 베팅금 대비 순이익 요약
    payouts = st.session_state.get("mg_payouts", [])
    contribs = st.session_state.get("mg_all_contribs", [])
    win_summaries = []

    for p_i, amt in enumerate(payouts):
        if amt > 0:
            p_name = get_player_name(p_i)
            c_amt = contribs[p_i] if p_i < len(contribs) else 0
            net_profit = amt - c_amt
            sign = "+" if net_profit >= 0 else ""
            win_summaries.append(
                f"**{p_name}** (총 베팅: **{c_amt} 칩** ➔ 수령: **{amt} 칩** | 순이익: **{sign}{net_profit} 칩**)"
            )

    if win_summaries:
        summary_lines = "\n\n".join([f"• {item}" for item in win_summaries])
        st.info(f"💡 **최종 칩 수령 및 손익 차액 요약:**\n\n{summary_lines}")

    if st.session_state.mg_user_chips <= 0 and not st.session_state.mg_user_eliminated and st.session_state.mg_stage == "IDLE":
        if st.session_state.mg_user_rebuys > 0:
            st.error(f"⚠️ 보유 칩이 모두 소진되었습니다! Re-buy in을 진행하시겠습니까? (남은 횟수: {st.session_state.mg_user_rebuys}/{rebuy_setting})")
            r_col1, r_col2 = st.columns(2)
            if r_col1.button(f"🔄 Re-buy in ({start_chips_setting} 칩 충전) 및 다음 핸드", type="primary", use_container_width=True):
                st.session_state.mg_user_chips = start_chips_setting
                st.session_state.mg_user_rebuys -= 1
                start_new_hand()
                st.rerun()
            if r_col2.button("👀 관전하기 / 기권", use_container_width=True):
                st.session_state.mg_user_eliminated = True
                st.session_state.mg_hero_cards = []
                st.rerun()
        else:
            st.error(f"😭 모든 Re-buy in({rebuy_setting}회)을 소진하셨습니다. 관전 모드로 전환됩니다.")

    sb_pos, bb_pos, _ = get_positions(st.session_state.mg_dealer_pos, active_indices)

    # 1) 상대 AI 현황
    st.markdown("### 🤖 상대 AI 플레이어 현황")
    opp_cols = st.columns(min(opponents_count, 9))
    
    for idx in range(opponents_count):
        p_idx = idx + 1
        pos_tag = ""
        if p_idx == st.session_state.mg_dealer_pos: pos_tag = " [BTN]"
        elif p_idx == sb_pos: pos_tag = " [SB]"
        elif p_idx == bb_pos: pos_tag = " [BB]"

        with opp_cols[idx]:
            chip_val = st.session_state.mg_opp_chips[idx] if idx < len(st.session_state.mg_opp_chips) else start_chips_setting
            bet_val = st.session_state.mg_opp_bets[idx] if idx < len(st.session_state.mg_opp_bets) else 0
            total_contrib_val = st.session_state.mg_opp_total_contribs[idx] if idx < len(st.session_state.mg_opp_total_contribs) else 0
            rebuy_left = st.session_state.mg_opp_rebuys[idx] if idx < len(st.session_state.mg_opp_rebuys) else rebuy_setting
            is_elim = is_player_eliminated(p_idx)
            is_folded = is_player_folded(p_idx)
            
            allin_tag = " <span style='color:#ef4444; font-weight:bold;'>(🔥 ALL IN)</span>" if (chip_val == 0 and not is_elim and not is_folded) else ""
            
            st.markdown(f"""
                **AI {idx+1}**{pos_tag}<br>
                <small style='color:#60a5fa;'>
                    <b>칩: {chip_val}</b> (리바이: {rebuy_left}/{rebuy_setting})<br>
                    <b>라운드 베팅액: {bet_val}</b><br>
                    <b>핸드 누적 베팅액: {total_contrib_val}</b>{allin_tag}
                </small>
            """, unsafe_allow_html=True)
            
            if is_elim:
                st.markdown("<span style='color:gray;'>💀 탈락 (Out)</span>", unsafe_allow_html=True)
            elif is_folded:
                st.markdown("<span style='color:red;'>🏳️ Fold</span>", unsafe_allow_html=True)
            else:
                if st.session_state.mg_stage in ["SHOWDOWN", "IDLE"] and st.session_state.mg_showdown_done:
                    opp_cards = st.session_state.mg_opp_cards_list[idx] if idx < len(st.session_state.mg_opp_cards_list) else []
                    opp_h = "".join([format_card_html(c) for c in opp_cards])
                    opp_rank = get_best_korean_hand(opp_cards, st.session_state.mg_board_cards)
                    st.markdown(f"{opp_h}<br><small style='color:#f59e0b; font-weight:bold;'>{opp_rank}</small>", unsafe_allow_html=True)
                else:
                    st.markdown("<span style='font-size:1.2rem;'>🂠 🂠</span>", unsafe_allow_html=True)

            ai_logs = st.session_state.mg_player_histories.get(f"AI {idx+1}", [])
            if ai_logs:
                badge_html = " ".join(ai_logs[-2:])
                st.markdown(f"<div class='player-action-box'>{badge_html}</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='player-action-box'><small style='color:gray;'>대기 중</small></div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### 🃏 커뮤니티 보드")
    if st.session_state.mg_board_cards:
        st.markdown("".join([format_card_html(c) for c in st.session_state.mg_board_cards]), unsafe_allow_html=True)
    else:
        st.markdown("<span style='color:gray;'>[ 프리플랍 진행 중 - 커뮤니티 카드 없음 ]</span>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    
    # 2) 내(Hero) 현황
    hero_tag = ""
    if st.session_state.mg_dealer_pos == 0: hero_tag = " [BTN]"
    elif sb_pos == 0: hero_tag = " [SB]"
    elif bb_pos == 0: hero_tag = " [BB]"

    if st.session_state.mg_user_eliminated:
        hero_h = "<span style='color:#ef4444; font-weight:bold;'>👀 [관전 모드 - 내 패 없음]</span>"
        hero_rank_str = ""
    else:
        hero_h = "".join([format_card_html(c) for c in st.session_state.mg_hero_cards]) if st.session_state.mg_hero_cards else "<span style='color:gray;'>[ 카드 없음 ]</span>"
        hero_rank_str = f" `({get_best_korean_hand(st.session_state.mg_hero_cards, st.session_state.mg_board_cards)})`" if len(st.session_state.mg_hero_cards + st.session_state.mg_board_cards) >= 5 else ""
    
    hero_allin_tag = " <span style='color:#ef4444; font-weight:bold;'>(🔥 ALL IN)</span>" if (st.session_state.mg_user_chips == 0 and not st.session_state.mg_user_eliminated and not st.session_state.mg_user_folded) else ""

    hero_col1, hero_col2 = st.columns([2, 1])
    with hero_col1:
        st.markdown(f"### 👤 내 핸드{hero_tag}: {hero_h}{hero_rank_str}", unsafe_allow_html=True)
        st.markdown(f"""
            <div style="font-size:0.92rem; color:{text_sub}; margin-top:2px;">
                💰 내 보유 칩: <b>{st.session_state.mg_user_chips}</b> &nbsp;|&nbsp; 
                현재 라운드 베팅액: <b>{st.session_state.mg_user_bet}</b> &nbsp;|&nbsp; 
                이번 핸드 누적 베팅액: <b>{st.session_state.mg_user_total_contrib}</b>{hero_allin_tag}
            </div>
        """, unsafe_allow_html=True)

    with hero_col2:
        hero_logs = st.session_state.mg_player_histories.get("Hero", [])
        if hero_logs:
            h_badge_html = " ".join(hero_logs[-2:])
            st.markdown(f"<div class='player-action-box'><b>내 행동 칩:</b><br>{h_badge_html}</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='player-action-box'><small style='color:gray;'>대기 중</small></div>", unsafe_allow_html=True)

    # 3) 대기 모드 및 액션 영역
    if st.session_state.mg_stage == "IDLE":
        st.markdown("---")
        if active_players_count == 1:
            if not st.session_state.mg_user_eliminated:
                st.balloons()
                st.success("🏆 **축하합니다! 모든 상대 AI를 제치고 토너먼트 최종 1인 우승자가 되었습니다!**")
            else:
                st.error("😭 **안타깝게도 최종 탈락하셨습니다.**")
        
        col_start1, col_start2 = st.columns([2, 1])
        with col_start1:
            st.info(f"💡 설정: **상대 AI {opponents_count}명** | **시작 칩 {start_chips_setting}** | **리바이 {rebuy_setting}회** | **BB {bb_setting} (SB {sb_setting})**")
        with col_start2:
            if st.button("🔄 전체 토너먼트 새로 시작", type="primary", use_container_width=True):
                reset_entire_tournament()
                start_new_hand()
                st.rerun()

        if active_players_count > 1 and st.button("🃏 다음 핸드 진행하기", type="primary", use_container_width=True):
            start_new_hand()
            st.rerun()

    else:
        st.markdown("---")
        st.subheader("💡 내 실시간 승률 & 실시간 팟 오즈")
        
        live_active_opp = sum(
            1 for idx in range(opponents_count) 
            if not is_player_eliminated(idx + 1) and not is_player_folded(idx + 1)
        )
        call_needed = max(0, st.session_state.mg_current_max_bet - st.session_state.mg_user_bet)

        if not st.session_state.mg_user_eliminated and live_active_opp > 0 and len(st.session_state.mg_board_cards) in (0, 3, 4, 5):
            try:
                h_treys = [Card.new(c) for c in st.session_state.mg_hero_cards]
                b_treys = [Card.new(c) for c in st.session_state.mg_board_cards]
                eq, _, _, _ = calculate_monte_carlo_equity(h_treys, b_treys, live_active_opp, iterations=1000)
                live_eq = eq * 100.0
            except: live_eq = 0.0
        else: live_eq = 0.0

        if call_needed > 0:
            live_req_eq = (call_needed / (st.session_state.mg_pot + call_needed)) * 100.0
            ratio_val = round((st.session_state.mg_pot + call_needed) / call_needed, 1)
            odds_str = f"팟 오즈 비율 {ratio_val} : 1 (필요 칩: {call_needed} 칩)"
            req_eq_display = f"{live_req_eq:.1f}%"
            commentary_msg = f"💡 **실시간 상황 해설:** 상대의 베팅/레이즈로 인해 콜에 **{call_needed} 칩**이 필요합니다. 수학적 팟 오즈 필요 승률은 **{live_req_eq:.1f}%**이며, 현재 내 승률(**{live_eq:.1f}%**)이 더 크다면 **+EV(양의 기대값)** 콜 구간입니다."
            commentary_type = "info" if live_eq >= live_req_eq else "warning"
        else:
            live_req_eq = 0.0
            odds_str = "체크 가능 (추가 지출 0 칩)"
            req_eq_display = "0.0% <span style='font-size:1.0rem; color:#22c55e;'>(체크 가능 - 필요 칩 0)</span>"
            commentary_msg = "💡 **실시간 상황 해설:** 현재 상대들의 체크로 추가 지출 칩이 0원(Call Needed = 0)인 **체크 가능 상황**입니다. 베팅 없이 무료로 다음 카드나 쇼다운을 볼 수 있으므로 필요 승률은 **0.0%**입니다."
            commentary_type = "info"

        adv1, adv2 = st.columns(2)
        adv1.markdown(f"""
            <div style="background-color:{card_bg}; border:2px solid #22c55e; border-radius:8px; padding:12px; text-align:center;">
                <div style="color:#4ade80; font-size:0.95rem; font-weight:bold;">🎲 내 수학적 실시간 승률 (생존 상대 {live_active_opp}명)</div>
                <div style="font-size:1.8rem; font-weight:bold; color:{text_main}; margin:6px 0;">{live_eq:.1f}%</div>
            </div>
        """, unsafe_allow_html=True)

        adv2.markdown(f"""
            <div style="background-color:{card_bg}; border:2px solid #3b82f6; border-radius:8px; padding:12px; text-align:center;">
                <div style="color:#60a5fa; font-size:0.95rem; font-weight:bold;">📐 동적 콜 필요 승률 (콜 필요: {call_needed} 칩)</div>
                <div style="font-size:1.8rem; font-weight:bold; color:{text_main}; margin:6px 0;">{req_eq_display}</div>
                <div style="font-size:0.8rem; color:{text_sub};">{odds_str}</div>
            </div>
        """, unsafe_allow_html=True)

        if commentary_type == "info":
            st.info(commentary_msg)
        else:
            st.warning(commentary_msg)

        st.markdown("<br>", unsafe_allow_html=True)

        # -----------------------------------------------------------------
        # [핵심 보완] 올인 시 수동 오픈 진행 및 베팅 컨트롤부
        # -----------------------------------------------------------------
        bettable_players = [i for i in range(total_players) if not is_player_eliminated(i) and not is_player_folded(i) and get_player_chips(i) > 0]
        no_more_betting = (len(bettable_players) <= 1)

        if st.session_state.mg_user_eliminated:
            st.info("👀 **관전 모드 진행 중입니다. AI 플레이어들의 승부가 진행됩니다.**")
            if st.button("⏩ 관전 진행 (AI 턴 진행)", type="primary", use_container_width=True):
                run_poker_turn_engine()
                st.rerun()

        elif st.session_state.mg_user_folded:
            st.info("🏳️ **현재 폴드(Fold) 상태입니다. 남은 AI 플레이어들의 승부가 자동 진행됩니다.**")
            if st.button("⏩ AI 승부 진행 / 다음 단계로", type="primary", use_container_width=True):
                st.session_state.mg_active_turn = get_next_turn(st.session_state.mg_active_turn)
                run_poker_turn_engine()
                st.rerun()

        # [올인 수동 진행 처리] 추가 베팅이 더 이상 불가능한 모든 플레이어 올인 상황
        elif no_more_betting:
            st.warning("🔥 **올인(ALL IN) 승부 진행 중입니다! 아래 버튼을 클릭해 카드를 한 장씩 오픈하며 결과를 확인하세요.**")
            stage_btn_map = {
                "PREFLOP": "🃏 플랍(Flop) 3장 카드 오픈하기 ⏩",
                "FLOP": "🃏 턴(Turn) 카드 오픈하기 ⏩",
                "TURN": "🃏 리버(River) 카드 오픈하기 ⏩",
                "RIVER": "🏆 최종 쇼다운 & 팟 정산 결과 확인하기 ⏩"
            }
            btn_label = stage_btn_map.get(st.session_state.mg_stage, "⏩ 다음 단계 진행")
            if st.button(btn_label, type="primary", use_container_width=True):
                advance_poker_street()
                st.rerun()

        else:
            cur_p = st.session_state.mg_active_turn
            if cur_p != 0:
                st.info("⏳ **상대 AI 플레이어들이 생각하고 베팅 중입니다...**")
                if st.button("▶️ AI 턴 진행하기", type="primary", use_container_width=True):
                    run_poker_turn_engine()
                    st.rerun()
            else:
                st.write(f"⚡ **[내 차례입니다] 액션 선택 (현재 라운드 콜 필요액: {call_needed} 칩):**")
                cur_stg = st.session_state.mg_stage
                
                min_raise_amt = call_needed + bb_setting
                max_raise_amt = st.session_state.mg_user_chips
                
                act_col1, act_col2, act_col3 = st.columns([1.2, 2, 1])

                if call_needed == 0:
                    if act_col1.button("✅ 체크 (지출 0 칩 | 라운드 총액: " + str(st.session_state.mg_user_bet) + " 칩)", use_container_width=True):
                        add_player_action("Hero", "CHECK", "Check")
                        st.session_state.mg_acted_players.append(0)
                        st.session_state.mg_active_turn = get_next_turn(0)
                        run_poker_turn_engine()
                        st.rerun()
                else:
                    actual_call = min(call_needed, st.session_state.mg_user_chips)
                    total_call_bet = st.session_state.mg_user_bet + actual_call
                    is_hero_call_allin = (st.session_state.mg_user_chips - actual_call == 0)
                    btn_call_text = f"📞 콜 (지출 {actual_call} 칩 | 라운드 총액: {total_call_bet} 칩)"
                    if is_hero_call_allin:
                        btn_call_text += " (ALL IN)"

                    if act_col1.button(btn_call_text, use_container_width=True):
                        st.session_state.mg_user_chips -= actual_call
                        st.session_state.mg_pot += actual_call
                        st.session_state.mg_user_bet += actual_call
                        st.session_state.mg_user_total_contrib += actual_call
                        act_detail = f"Call {actual_call} (ALL IN)" if is_hero_call_allin else f"Call {actual_call}"
                        add_player_action("Hero", "CALL", act_detail)
                        st.session_state.mg_acted_players.append(0)
                        st.session_state.mg_active_turn = get_next_turn(0)
                        run_poker_turn_engine()
                        st.rerun()

                with act_col2:
                    if min_raise_amt <= max_raise_amt:
                        custom_raise_val = st.number_input(
                            f"🔺 이번 턴 지출 금액 (최소 {min_raise_amt} ~ 최대 {max_raise_amt} 칩):",
                            min_value=int(min_raise_amt),
                            max_value=int(max_raise_amt),
                            value=int(min_raise_amt),
                            step=int(bb_setting),
                            key="raise_num_input"
                        )
                        total_raise_bet = st.session_state.mg_user_bet + custom_raise_val
                        is_hero_raise_allin = (st.session_state.mg_user_chips - custom_raise_val == 0)
                        btn_raise_label = f"🔺 레이즈 실행 (이번 턴 {custom_raise_val} 칩 지출 | 라운드 총액: {total_raise_bet} 칩)"
                        if is_hero_raise_allin:
                            btn_raise_label += " (ALL IN)"
                        
                        if st.button(btn_raise_label, use_container_width=True):
                            st.session_state.mg_user_chips -= custom_raise_val
                            st.session_state.mg_pot += custom_raise_val
                            st.session_state.mg_user_bet += custom_raise_val
                            st.session_state.mg_user_total_contrib += custom_raise_val
                            st.session_state.mg_current_max_bet = max(st.session_state.mg_current_max_bet, st.session_state.mg_user_bet)
                            act_detail = f"Raise +{custom_raise_val} (ALL IN)" if is_hero_raise_allin else f"Raise +{custom_raise_val}"
                            add_player_action("Hero", "RAISE", act_detail)
                            st.session_state.mg_acted_players = [0]
                            st.session_state.mg_active_turn = get_next_turn(0)
                            run_poker_turn_engine()
                            st.rerun()
                    else:
                        allin_amt = st.session_state.mg_user_chips
                        total_allin_bet = st.session_state.mg_user_bet + allin_amt
                        if st.button(f"🔥 올인 (이번 턴 {allin_amt} 칩 지출 | 라운드 총액: {total_allin_bet} 칩)", use_container_width=True):
                            st.session_state.mg_pot += allin_amt
                            st.session_state.mg_user_bet += allin_amt
                            st.session_state.mg_user_total_contrib += allin_amt
                            st.session_state.mg_user_chips = 0
                            st.session_state.mg_current_max_bet = max(st.session_state.mg_current_max_bet, st.session_state.mg_user_bet)
                            add_player_action("Hero", "RAISE", f"All-In {allin_amt} (ALL IN)")
                            st.session_state.mg_acted_players = [0]
                            st.session_state.mg_active_turn = get_next_turn(0)
                            run_poker_turn_engine()
                            st.rerun()

                if act_col3.button("🏳️ 폴드 (기권 | 지출 0 칩)", use_container_width=True):
                    st.session_state.mg_user_folded = True
                    add_player_action("Hero", "FOLD", "Fold")
                    st.session_state.mg_acted_players.append(0)
                    st.session_state.mg_active_turn = get_next_turn(0)
                    run_poker_turn_engine()
                    st.rerun()
