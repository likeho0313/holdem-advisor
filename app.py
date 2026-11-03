import random
import string
import itertools
from collections import Counter
import streamlit as st
from treys import Card, Deck, Evaluator

# ==========================================
# 0. 페이지 기본 설정 및 글로벌 룸 세션 관리
# ==========================================
st.set_page_config(
    page_title="텍사스 홀덤 실시간 승률 & 멀티 토너먼트 모의게임",
    page_icon="♠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 서버 전체 사용자 간 방 공유를 위한 메모리 렌더러
@st.cache_resource
def get_global_rooms():
    return {}

GLOBAL_ROOMS = get_global_rooms()

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

# --- [멀티플레이 접속 상태] ---
if "current_room_code" not in st.session_state:
    st.session_state.current_room_code = None
if "my_player_name" not in st.session_state:
    st.session_state.my_player_name = "Player_1"

# --- [단일 모의게임 세션 상태] ---
if "mg_stage" not in st.session_state:
    st.session_state.mg_stage = "IDLE"
if "mg_user_chips" not in st.session_state:
    st.session_state.mg_user_chips = 400
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
    st.session_state.mg_dealer_pos = 0
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
# 1. 169 핸드 티어 정의
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
# 2. 사이드바 설정 (모드 & 방 관리)
# ==========================================
st.sidebar.title("⚙️ 게임 설정 & 멀티룸")

view_mode = st.sidebar.radio("📱 화면 모드 선택", ["📱 모바일 모드", "💻 PC 모드"], index=0)
is_mobile = (view_mode == "📱 모바일 모드")

max_opponents = 3 if is_mobile else 9
opponents_count = st.sidebar.slider("상대 플레이어 수 (AI 포함)", min_value=1, max_value=max_opponents, value=min(3, max_opponents))

start_chips_setting = st.sidebar.slider("시작 칩 (Start Chips)", min_value=100, max_value=10000, value=400, step=100)
rebuy_setting = st.sidebar.slider("최대 리바이 가능 횟수", min_value=0, max_value=5, value=3, step=1)
bb_setting = st.sidebar.slider("빅 블라인드 (BB) 금액", min_value=10, max_value=500, value=20, step=10)
sb_setting = bb_setting // 2

sim_iterations = st.sidebar.select_slider("승률 정밀도", options=[1000, 2500, 5000], value=2500)

st.sidebar.markdown("---")
st.sidebar.subheader("🌐 멀티플레이 룸 매칭")

room_action = st.sidebar.radio("멀티플레이 기능", ["솔로 플레이", "방 생성하기", "방 참가하기"])

if room_action == "방 생성하기":
    max_total_p = st.sidebar.number_input("최대 전체 플레이어 수", min_value=2, max_value=10, value=4)
    human_p_cnt = st.sidebar.number_input("사람(인간) 플레이어 수", min_value=1, max_value=max_total_p, value=2)
    ai_bot_cnt = max_total_p - human_p_cnt
    st.sidebar.caption(f"🤖 자동 계산된 AI BOT 수: **{ai_bot_cnt}명**")
    
    if st.sidebar.button("🎲 방 생성 & 입장코드 발급", use_container_width=True):
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        GLOBAL_ROOMS[code] = {
            "max_players": max_total_p,
            "human_target": human_p_cnt,
            "ai_count": ai_bot_cnt,
            "joined_humans": [f"Player_1"],
            "start_chips": start_chips_setting,
            "rebuys": rebuy_setting,
            "bb": bb_setting
        }
        st.session_state.current_room_code = code
        st.session_state.my_player_name = "Player_1 (방장)"
        st.sidebar.success(f"방이 생성되었습니다! 코드: **{code}**")

elif room_action == "방 참가하기":
    join_code_input = st.sidebar.text_input("입장 코드를 입력하세요", max_chars=6).strip().upper()
    if st.sidebar.button("🚪 방 입장하기", use_container_width=True):
        if join_code_input in GLOBAL_ROOMS:
            room = GLOBAL_ROOMS[join_code_input]
            if len(room["joined_humans"]) < room["human_target"]:
                p_id = f"Player_{len(room['joined_humans']) + 1}"
                room["joined_humans"].append(p_id)
                st.session_state.current_room_code = join_code_input
                st.session_state.my_player_name = p_id
                st.sidebar.success(f"방 [{join_code_input}]에 {p_id}로 입장했습니다!")
            else:
                st.sidebar.error("해당 방의 인원이 이미 가득 찼습니다.")
        else:
            st.sidebar.error("존재하지 않거나 유효하지 않은 입장 코드입니다.")

if st.session_state.current_room_code:
    st.sidebar.info(f"🔑 현재 참가 중인 방: **{st.session_state.current_room_code}** ({st.session_state.my_player_name})")
    if st.sidebar.button("🚪 방 나가기"):
        st.session_state.current_room_code = None
        st.rerun()

st.sidebar.markdown("---")
theme_mode = st.sidebar.radio("🎨 UI 테마 선택", ["☀️ 라이트 모드", "🌙 다크 모드"], index=0)
is_dark = (theme_mode == "🌙 다크 모드")


# ==========================================
# 3. 테마 및 공통 헬퍼 함수
# ==========================================
if is_dark:
    app_bg, card_bg, text_main, text_sub, border_col = "#0f172a", "#1e293b", "#f8fafc", "#94a3b8", "#334155"
    bg_s, bg_a, bg_b, bg_c, bg_d = "#14532d", "#1e3a8a", "#713f12", "#581c87", "#1e293b"
    badge_txt = "#ffffff"
    txt_pair, txt_suited, txt_off = "#93c5fd", "#86efac", "#fdba74"
else:
    app_bg, card_bg, text_main, text_sub, border_col = "#f8fafc", "#ffffff", "#0f172a", "#475569", "#cbd5e1"
    bg_s, bg_a, bg_b, bg_c, bg_d = "#a7f3d0", "#bae6fd", "#fef08a", "#e9d5ff", "#ffffff"
    badge_txt = "#0f172a"
    txt_pair, txt_suited, txt_off = "#1d4ed8", "#15803d", "#c2410c"


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
    
    if is_mobile:
        if is_flush and is_mountain: return (13, ranks), "로얄 스플"
        elif is_flush and is_back_straight: return (12, ranks), "백 스플"
        elif is_flush and is_reg_straight: return (11, ranks[0]), f"스티플({RANK_NAME[ranks[0]]})"
        elif freq[0][0] == 4: return (10, freq[0][1], freq[1][1]), f"포카드({RANK_NAME[freq[0][1]]})"
        elif freq[0][0] == 3 and freq[1][0] == 2: return (9, freq[0][1], freq[1][1]), f"풀하우스({RANK_NAME[freq[0][1]]})"
        elif is_flush: return (8, ranks), f"플러쉬({RANK_NAME[ranks[0]]})"
        elif is_mountain: return (7, 14), "마운틴"
        elif is_back_straight: return (6, 5), "백스트레이트"
        elif is_reg_straight: return (5, ranks[0]), f"스트레이트({RANK_NAME[ranks[0]]})"
        elif freq[0][0] == 3: return (4, freq[0][1], [f[1] for f in freq[1:]]), f"트리플({RANK_NAME[freq[0][1]]})"
        elif freq[0][0] == 2 and freq[1][0] == 2: return (3, freq[0][1], freq[1][1], freq[2][1]), f"투페어({RANK_NAME[freq[0][1]]}&{RANK_NAME[freq[1][1]]})"
        elif freq[0][0] == 2: return (2, freq[0][1], [f[1] for f in freq[1:]]), f"원페어({RANK_NAME[freq[0][1]]})"
        else: return (1, ranks), f"노페어({RANK_NAME[ranks[0]]})"
    else:
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
    if len(all_cards) < 5: return "카드부족" if is_mobile else "보드 카드를 더 선택해주세요"
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


btn_height = "26px" if is_mobile else "34px"
btn_font_size = "0.68rem" if is_mobile else "0.82rem"

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
            extra_style = "font-weight: 900 !important; box-shadow: 0 0 6px #f59e0b !important;"
        else:
            btn_bg, btn_txt, btn_border, extra_style = bg_col, txt_col, border_col, ""
        dynamic_button_styles.append(f"""
            div[class*="st-key-{key_id}"] button, div[class*="st-key-{key_id}"] button:hover {{
                background-color: {btn_bg} !important; border: 1px solid {btn_border} !important; {extra_style}
                min-height: {btn_height} !important; font-size: {btn_font_size} !important; padding: 0px !important;
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
                min-height: {btn_height} !important;
            }}
            div[class*="st-key-{key_id}"] button * {{ font-weight: bold !important; font-size: {btn_font_size} !important; }}
        """)

dynamic_button_styles.append("""
    div[class*="st-key-btn_next_hand"] button {
        background-color: #22c55e !important;
        border: 1px solid #16a34a !important;
    }
    div[class*="st-key-btn_next_hand"] button:hover {
        background-color: #16a34a !important;
        border: 1px solid #15803d !important;
    }
    div[class*="st-key-btn_next_hand"] button * {
        color: #ffffff !important;
        font-weight: bold !important;
    }
""")

mobile_header_css = """
    header[data-testid="stHeader"] { background: transparent !important; height: 0px !important; min-height: 0px !important; }
    [data-testid="stSidebarCollapsedControl"] {
        display: block !important; position: fixed !important; bottom: 15px !important; left: 15px !important; top: auto !important; z-index: 999999 !important;
        background-color: #1e293b !important; border: 1px solid #475569 !important; border-radius: 50% !important; padding: 4px !important;
    }
""" if is_mobile else ""

st.markdown(f"""
    <style>
    {mobile_header_css}
    .main .block-container {{ padding-top: {"0.2rem" if is_mobile else "1rem"} !important; padding-bottom: {"0.2rem" if is_mobile else "1rem"} !important; padding-left: {"0.2rem" if is_mobile else "1rem"} !important; padding-right: {"0.2rem" if is_mobile else "1rem"} !important; }}
    div[data-testid="stVerticalBlock"] > div {{ gap: {"0.15rem" if is_mobile else "0.4rem"} !important; }}
    footer, #MainMenu, div[data-testid="stDecoration"], div[data-testid="stStatusWidget"], div[class*="viewerBadge"], a[href*="streamlit.io"] {{ display: none !important; }}
    .stApp {{ background-color: {app_bg} !important; color: {text_main} !important; }}
    div[data-testid="stHorizontal"] > div {{ padding: 0px 1px !important; }}
    .stButton button {{ width: 100% !important; padding: 1px 0px !important; font-size: {btn_font_size} !important; min-height: {btn_height} !important; border-radius: 4px !important; }}
    {" ".join(dynamic_button_styles)}
    .tier-badge {{ display: inline-block; padding: 1px 3px; border-radius: 3px; font-weight: bold; font-size: 0.7rem; margin: 0 1px; }}
    .tier-badge-s {{ background-color: {bg_s} !important; color: {badge_txt} !important; }}
    .tier-badge-a {{ background-color: {bg_a} !important; color: {badge_txt} !important; }}
    .tier-badge-b {{ background-color: {bg_b} !important; color: {badge_txt} !important; }}
    .tier-badge-c {{ background-color: {bg_c} !important; color: {badge_txt} !important; }}
    .tier-badge-d {{ background-color: {bg_d} !important; color: {badge_txt} !important; border: 1px solid {border_col} !important; }}
    .card-badge {{ display: inline-block; padding: 1px 4px; font-size: {"0.8rem" if is_mobile else "1.0rem"}; font-weight: bold; border-radius: 4px; margin: 0px 1px; }}
    .suit-s, .suit-c {{ background-color: #1e293b; color: #ffffff; border: 1px solid #475569; }}
    .suit-h, .suit-d {{ background-color: #450a0a; color: #f87171; border: 1px solid #991b1b; }}
    .poker-chip {{ display: inline-flex; align-items: center; gap: 1px; padding: 1px 3px; border-radius: 6px; font-weight: bold; font-size: 0.65rem; box-shadow: 0 1px 2px rgba(0,0,0,0.15); margin: 0px 1px; white-space: nowrap; }}
    .chip-sb {{ background-color: #fef08a; color: #854d0e; border: 1px solid #eab308; }}
    .chip-bb {{ background-color: #fed7aa; color: #9a3412; border: 1px solid #f97316; }}
    .chip-call {{ background-color: #bbf7d0; color: #166534; border: 1px solid #22c55e; }}
    .chip-check {{ background-color: #e0f2fe; color: #075985; border: 1px solid #38bdf8; }}
    .chip-raise {{ background-color: #fecaca; color: #991b1b; border: 1px solid #ef4444; font-weight: 900; }}
    .chip-fold {{ background-color: #f1f5f9; color: #64748b; border: 1px solid #94a3b8; }}
    .opp-card-box {{ background-color: {card_bg}; border: 1px solid {border_col}; border-radius: 5px; padding: 3px 5px; font-size: 0.7rem; line-height: 1.2; }}
    .hero-board-box {{ background-color: {card_bg}; border: 1px solid {border_col}; border-radius: 5px; padding: 4px 6px; margin-bottom: 2px; }}
    .player-action-box {{ background-color: {card_bg}; border: 1px solid {border_col}; border-radius: 6px; padding: 6px 8px; font-size: 0.78rem; margin-top: 6px; line-height: 1.4; min-height: 48px; }}
    </style>
""", unsafe_allow_html=True)


# ==========================================
# 4. 탭 구성
# ==========================================
tab_advisor, tab_game = st.tabs(["📊 실시간 승률 & 수학적 어드바이저", "🎮 1:N 토너먼트 모의게임"])

# [TAB 1] 생략 없이 동일 유지
with tab_advisor:
    if is_mobile:
        st.markdown("### ♠️ 실시간 홀덤 승률 & 수학적 어드바이저")
    else:
        st.title("♠️ 실시간 홀덤 승률 & 수학적 어드바이저")

    matrix_cols = st.columns([0.4 if is_mobile else 0.6] + [1]*13)
    matrix_cols[0].write("")
    for j, r in enumerate(RANKS): matrix_cols[j+1].markdown(f"**{r}**")
        
    for i, r1 in enumerate(RANKS):
        m_row = st.columns([0.4 if is_mobile else 0.6] + [1]*13)
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

    h1, h2 = st.session_state.hero_card1, st.session_state.hero_card2
    r1, r2 = h1[0], h2[0]
    hero_cards = [h1, h2]
    h_html = "".join([format_card_html(c) for c in hero_cards])
    st.markdown(f"**내 핸드:** {h_html} `({hand_type(r1, r2)})`", unsafe_allow_html=True)

    st.write("🃏 **보드 카드 선택 (플랍/턴/리버):**")
    used_cards = set(hero_cards + st.session_state.board_cards)
    slot_cols = st.columns(5)
    slot_names = ["플랍1", "플랍2", "플랍3", "턴", "리버"]

    for i in range(5):
        with slot_cols[i]:
            st.caption(f"**{slot_names[i]}**")
            if i < len(st.session_state.board_cards):
                card_code = st.session_state.board_cards[i]
                st.markdown(format_card_html(card_code), unsafe_allow_html=True)
                if st.button("❌", key=f"remove_board_{i}", use_container_width=True):
                    st.session_state.board_cards.pop(i)
                    st.rerun()
            else:
                st.markdown("<div style='color:gray; font-size:0.75rem;'>[빈슬롯]</div>", unsafe_allow_html=True)

    for s in SUITS:
        suit_row = st.columns([0.5 if is_mobile else 0.8] + [1]*13)
        suit_row[0].markdown(f"**{get_suit_md(s)}**")
        for j, r in enumerate(RANKS):
            card_code = f"{r}{s}"
            btn_label = format_card_md(r, s)
            if card_code in used_cards:
                suit_row[j+1].markdown("<div style='min-height:26px;'></div>", unsafe_allow_html=True)
            else:
                if suit_row[j+1].button(btn_label, key=f"pick_card_{card_code}", disabled=len(st.session_state.board_cards)>=5, use_container_width=True):
                    if len(st.session_state.board_cards) < 5:
                        st.session_state.board_cards.append(card_code)
                        st.rerun()

    board_cards = st.session_state.board_cards
    if len(board_cards) in (0, 3, 4, 5):
        try:
            hero_treys = [Card.new(c) for c in hero_cards]
            board_treys = [Card.new(c) for c in board_cards]
            equity, win_rate, tie_rate, loss_rate = calculate_monte_carlo_equity(hero_treys, board_treys, opponents_count, sim_iterations)
            eq_pct = equity * 100.0
            st.info(f"🎲 **계산된 내 승률 ({opponents_count}명 기준):** {eq_pct:.1f}%")
        except Exception as e:
            st.error(f"승률 계산 오류: {str(e)}")


# ==========================================
# [TAB 2] 1:N 토너먼트 모의게임
# ==========================================
with tab_game:
    total_players = opponents_count + 1

    def is_player_eliminated(p_idx):
        if p_idx == 0: return st.session_state.mg_user_eliminated
        else:
            ai_i = p_idx - 1
            return st.session_state.mg_opp_eliminated[ai_i] if ai_i < len(st.session_state.mg_opp_eliminated) else True

    def is_player_folded(p_idx):
        if p_idx == 0: return st.session_state.mg_user_folded or st.session_state.mg_user_eliminated
        else:
            ai_i = p_idx - 1
            return (st.session_state.mg_opp_folded[ai_i] or st.session_state.mg_opp_eliminated[ai_i]) if ai_i < len(st.session_state.mg_opp_folded) else True

    def get_player_chips(p_idx):
        if p_idx == 0: return st.session_state.mg_user_chips
        else:
            ai_i = p_idx - 1
            return st.session_state.mg_opp_chips[ai_i] if ai_i < len(st.session_state.mg_opp_chips) else 0

    def get_player_name(p_idx):
        return "Hero" if p_idx == 0 else f"AI {p_idx}"

    def get_active_player_indices():
        active = []
        if not st.session_state.mg_user_eliminated: active.append(0)
        for i in range(opponents_count):
            if i < len(st.session_state.mg_opp_eliminated) and not st.session_state.mg_opp_eliminated[i]:
                active.append(i + 1)
        return active

    def get_next_turn(current_turn):
        for step in range(1, total_players + 1):
            nxt = (current_turn + step) % total_players
            if not is_player_eliminated(nxt): return nxt
        return current_turn

    def get_positions(dealer_pos, active_indices):
        num_active = len(active_indices)
        if num_active < 2: return 0, 0, 0
        d_idx = active_indices.index(dealer_pos) if dealer_pos in active_indices else 0
        if num_active == 2:
            return active_indices[d_idx], active_indices[(d_idx + 1) % 2], active_indices[d_idx]
        else:
            return active_indices[(d_idx + 1) % num_active], active_indices[(d_idx + 2) % num_active], active_indices[(d_idx + 3) % num_active]

    def add_player_action(player_name, action_type, detail_str):
        if player_name in st.session_state.mg_player_histories:
            st.session_state.mg_player_histories[player_name].append(format_action_chip_html(action_type, detail_str))

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
        st.session_state.mg_dealer_pos = 0
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
        
        scores, hand_descs = {}, {}
        if not all_folded[0]:
            h_treys = [Card.new(c) for c in st.session_state.mg_hero_cards]
            scores[0] = EVALUATOR.evaluate(b_treys, h_treys)
            hand_descs[0] = get_best_korean_hand(st.session_state.mg_hero_cards, st.session_state.mg_board_cards)
        
        for idx in range(opponents_count):
            p_id = idx + 1
            if not all_folded[p_id]:
                opp_cards = st.session_state.mg_opp_cards_list[idx]
                scores[p_id] = EVALUATOR.evaluate(b_treys, [Card.new(c) for c in opp_cards])
                hand_descs[p_id] = get_best_korean_hand(opp_cards, st.session_state.mg_board_cards)

        active_caps = sorted(list(set([all_contribs[i] for i in range(total_players) if not all_folded[i] and all_contribs[i] > 0])))
        if not active_caps: active_caps = sorted(list(set([c for c in all_contribs if c > 0])))

        payouts = [0] * total_players
        prev_cap = 0
        pot_rows = []

        for cap_idx, cap in enumerate(active_caps):
            slice_pot = sum(max(0, min(all_contribs[i], cap) - prev_cap) for i in range(total_players))
            prev_cap = cap
            if slice_pot <= 0: continue

            eligible_players = [i for i in range(total_players) if all_contribs[i] >= cap and not all_folded[i]]
            if not eligible_players: eligible_players = [i for i in range(total_players) if not all_folded[i]]

            if eligible_players:
                best_score = min([scores[i] for i in eligible_players])
                winners = [i for i in eligible_players if scores[i] == best_score]
                split_amt = slice_pot // len(winners)
                for w in winners: payouts[w] += split_amt
                
                pot_rows.append({
                    "label": "🥇 메인 팟" if cap_idx == 0 else f"🪙 사이드 팟 {cap_idx}",
                    "pot_amt": slice_pot,
                    "cap_amt": cap,
                    "eligible": ", ".join([get_player_name(p) for p in eligible_players]),
                    "winners": ", ".join([f"{get_player_name(w)} (+{split_amt} 칩)" for w in winners]),
                    "hands": " / ".join([hand_descs[w] for w in winners])
                })

        st.session_state.mg_user_chips += payouts[0]
        for idx in range(opponents_count):
            if idx < len(st.session_state.mg_opp_chips):
                st.session_state.mg_opp_chips[idx] += payouts[idx+1]

        st.session_state.mg_pot_details_rows = pot_rows
        st.session_state.mg_payouts = payouts
        st.session_state.mg_result_msg = "🏆 쇼다운이 완료되었습니다."
        st.session_state.mg_stage = "IDLE"

    def advance_poker_street():
        st.session_state.mg_user_bet = 0
        st.session_state.mg_opp_bets = [0] * opponents_count
        st.session_state.mg_current_max_bet = 0
        st.session_state.mg_acted_players = []
        
        active_idxs = get_active_player_indices()
        sb_p, bb_p, _ = get_positions(st.session_state.mg_dealer_pos, active_idxs)
        st.session_state.mg_active_turn = bb_p if len(active_idxs) == 2 else sb_p

        bettable = [i for i in range(total_players) if not is_player_eliminated(i) and not is_player_folded(i) and get_player_chips(i) > 0]
        no_more_betting = (len(bettable) <= 1)

        if st.session_state.mg_stage == "PREFLOP":
            st.session_state.mg_board_cards = [st.session_state.mg_deck.pop() for _ in range(3)]
            st.session_state.mg_stage = "FLOP"
            if not no_more_betting: run_poker_turn_engine()
        elif st.session_state.mg_stage == "FLOP":
            st.session_state.mg_board_cards.append(st.session_state.mg_deck.pop())
            st.session_state.mg_stage = "TURN"
            if not no_more_betting: run_poker_turn_engine()
        elif st.session_state.mg_stage == "TURN":
            st.session_state.mg_board_cards.append(st.session_state.mg_deck.pop())
            st.session_state.mg_stage = "RIVER"
            if not no_more_betting: run_poker_turn_engine()
        elif st.session_state.mg_stage == "RIVER":
            resolve_showdown_with_side_pots()

    def run_poker_turn_engine():
        max_loop_guard = 50
        loop_cnt = 0
        while loop_cnt < max_loop_guard:
            loop_cnt += 1
            curr_p = st.session_state.mg_active_turn
            active_opps = sum(1 for i in range(opponents_count) if not is_player_eliminated(i + 1) and not is_player_folded(i + 1))
            hero_act = not is_player_eliminated(0) and not is_player_folded(0)

            if (active_opps + (1 if hero_act else 0)) <= 1:
                payouts = [0] * total_players
                if hero_act:
                    payouts[0] = st.session_state.mg_pot
                    st.session_state.mg_user_chips += st.session_state.mg_pot
                    st.session_state.mg_result_msg = f"🎉 상대 기권으로 Hero 승리 (+{st.session_state.mg_pot} 칩)"
                else:
                    win_ai = next((i for i in range(opponents_count) if not is_player_eliminated(i + 1) and not is_player_folded(i + 1)), 0)
                    payouts[win_ai + 1] = st.session_state.mg_pot
                    st.session_state.mg_opp_chips[win_ai] += st.session_state.mg_pot
                    st.session_state.mg_result_msg = f"😭 AI {win_ai+1} 승리 (+{st.session_state.mg_pot} 칩)"
                st.session_state.mg_payouts = payouts
                st.session_state.mg_stage = "IDLE"
                break

            round_done = True
            for i in range(total_players):
                if is_player_eliminated(i) or is_player_folded(i) or get_player_chips(i) == 0: continue
                p_bet = st.session_state.mg_user_bet if i == 0 else st.session_state.mg_opp_bets[i - 1]
                if i not in st.session_state.mg_acted_players or p_bet < st.session_state.mg_current_max_bet:
                    round_done = False
                    break

            if round_done:
                advance_poker_street()
                break

            if is_player_eliminated(curr_p) or is_player_folded(curr_p) or get_player_chips(curr_p) == 0:
                if curr_p not in st.session_state.mg_acted_players: st.session_state.mg_acted_players.append(curr_p)
                st.session_state.mg_active_turn = get_next_turn(curr_p)
                continue

            if curr_p == 0: break

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
                    add_player_action(f"AI {ai_i+1}", "RAISE", f"Raise +{raise_amt}")
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
                    add_player_action(f"AI {ai_i+1}", "CALL", f"Call {actual_call}")
                    st.session_state.mg_acted_players.append(curr_p)
            else:
                if rnd < 0.15 and ai_chips >= bb_setting:
                    raise_amt = min(bb_setting, ai_chips)
                    st.session_state.mg_opp_chips[ai_i] -= raise_amt
                    st.session_state.mg_opp_bets[ai_i] += raise_amt
                    st.session_state.mg_opp_total_contribs[ai_i] += raise_amt
                    st.session_state.mg_pot += raise_amt
                    st.session_state.mg_current_max_bet = max(st.session_state.mg_current_max_bet, st.session_state.mg_opp_bets[ai_i])
                    add_player_action(f"AI {ai_i+1}", "BET", f"Bet {raise_amt}")
                    st.session_state.mg_acted_players = [curr_p]
                else:
                    add_player_action(f"AI {ai_i+1}", "CHECK", "Check")
                    st.session_state.mg_acted_players.append(curr_p)

            st.session_state.mg_active_turn = get_next_turn(curr_p)

    def start_new_hand():
        # --- [버그 수정: Hero 칩 0일 때 자동/수동 리바이 처리] ---
        if st.session_state.mg_user_chips <= 0:
            if st.session_state.mg_user_rebuys > 0:
                st.session_state.mg_user_chips = start_chips_setting
                st.session_state.mg_user_rebuys -= 1
                st.session_state.mg_user_eliminated = False
            else:
                st.session_state.mg_user_eliminated = True

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
        
        active_idxs = get_active_player_indices()
        if active_idxs:
            cur_d_i = active_idxs.index(st.session_state.mg_dealer_pos) if st.session_state.mg_dealer_pos in active_idxs else 0
            st.session_state.mg_dealer_pos = active_idxs[(cur_d_i + 1) % len(active_idxs)]

        sb_pos, bb_pos, utg_pos = get_positions(st.session_state.mg_dealer_pos, active_idxs)

        st.session_state.mg_pot = 0
        st.session_state.mg_user_bet = 0
        st.session_state.mg_opp_bets = [0] * opponents_count

        if sb_pos == 0 and not st.session_state.mg_user_eliminated:
            val = min(sb_setting, st.session_state.mg_user_chips)
            st.session_state.mg_user_chips -= val
            st.session_state.mg_user_bet = val
            st.session_state.mg_user_total_contrib += val
            st.session_state.mg_pot += val
            add_player_action("Hero", "SB", f"SB {val}")
        elif sb_pos > 0:
            ai_idx = sb_pos - 1
            if not is_player_eliminated(sb_pos):
                val = min(sb_setting, st.session_state.mg_opp_chips[ai_idx])
                st.session_state.mg_opp_chips[ai_idx] -= val
                st.session_state.mg_opp_bets[ai_idx] = val
                st.session_state.mg_opp_total_contribs[ai_idx] += val
                st.session_state.mg_pot += val
                add_player_action(f"AI {ai_idx+1}", "SB", f"SB {val}")

        if bb_pos == 0 and not st.session_state.mg_user_eliminated:
            val = min(bb_setting, st.session_state.mg_user_chips)
            st.session_state.mg_user_chips -= val
            st.session_state.mg_user_bet = val
            st.session_state.mg_user_total_contrib += val
            st.session_state.mg_pot += val
            add_player_action("Hero", "BB", f"BB {val}")
        elif bb_pos > 0:
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

    need_reset = (
        "mg_opp_chips" not in st.session_state or
        len(st.session_state.mg_opp_chips) != opponents_count or
        len(st.session_state.mg_opp_bets) != opponents_count
    )

    if need_reset: reset_entire_tournament()

    active_indices = get_active_player_indices()
    active_players_count = len(active_indices)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("👤 내 칩", f"{st.session_state.mg_user_chips}", f"리바이 {st.session_state.mg_user_rebuys}회")
    m2.metric("💰 팟", f"{st.session_state.mg_pot}")
    m3.metric("🏆 생존", f"{active_players_count}/{total_players} 명")
    m4.metric("📌 단계", st.session_state.mg_stage)

    sb_pos, bb_pos, _ = get_positions(st.session_state.mg_dealer_pos, active_indices)

    # 1) 상대 AI 영역
    st.write("🤖 **상대 AI 현황:**" if is_mobile else "### 🤖 상대 AI 플레이어 현황")
    cols_per_row = 3 if is_mobile else min(opponents_count, 9)
    for r_start in range(0, opponents_count, cols_per_row):
        r_opps = list(range(r_start, min(r_start + cols_per_row, opponents_count)))
        opp_cols = st.columns(len(r_opps))
        
        for col_i, idx in enumerate(r_opps):
            p_idx = idx + 1
            pos_tag = " [BTN]" if p_idx == st.session_state.mg_dealer_pos else (" [SB]" if p_idx == sb_pos else (" [BB]" if p_idx == bb_pos else ""))

            with opp_cols[col_i]:
                chip_val = st.session_state.mg_opp_chips[idx]
                bet_val = st.session_state.mg_opp_bets[idx]
                total_contrib_val = st.session_state.mg_opp_total_contribs[idx]
                rebuy_left = st.session_state.mg_opp_rebuys[idx]
                is_elim = is_player_eliminated(p_idx)
                is_folded = is_player_folded(p_idx)
                ai_logs = st.session_state.mg_player_histories.get(f"AI {idx+1}", [])
                latest_badges = " ".join(ai_logs[-2:]) if ai_logs else ""

                if is_mobile:
                    st.markdown(f"""
                        <div class="opp-card-box">
                            <b>AI {idx+1}</b>{pos_tag} {latest_badges}<br>
                            <span style="color:#60a5fa;"><b>칩: {chip_val}</b> ({rebuy_left}/{rebuy_setting})</span><br>
                            <span style="color:{text_sub};">라운드/누적: <b>{bet_val}/{total_contrib_val}</b></span>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"**AI {idx+1}**{pos_tag}<br><small style='color:#60a5fa;'><b>칩: {chip_val}</b> (리바이: {rebuy_left})</small>", unsafe_allow_html=True)

    # 2) 내 핸드 및 커뮤니티 보드
    hero_tag = " [BTN]" if st.session_state.mg_dealer_pos == 0 else (" [SB]" if sb_pos == 0 else (" [BB]" if bb_pos == 0 else ""))
    hero_h = "".join([format_card_html(c) for c in st.session_state.mg_hero_cards]) if st.session_state.mg_hero_cards else "[패 없음]"
    board_h = "".join([format_card_html(c) for c in st.session_state.mg_board_cards]) if st.session_state.mg_board_cards else "[프리플랍]"

    if is_mobile:
        st.markdown(f"""
            <div class="hero-board-box">
                <b>👤 내 핸드{hero_tag}:</b> {hero_h}<br>
                <b>🃏 보드:</b> {board_h}
            </div>
        """, unsafe_allow_html=True)
    else:
        hero_col1, hero_col2, hero_col3 = st.columns([2, 2, 1])
        with hero_col1: st.markdown(f"### 👤 내 핸드{hero_tag}: {hero_h}", unsafe_allow_html=True)
        with hero_col2: st.markdown(f"### 🃏 커뮤니티 보드: {board_h}", unsafe_allow_html=True)
        with hero_col3: st.markdown("<div class='player-action-box'><small style='color:gray;'>대기 중</small></div>", unsafe_allow_html=True)

    # 3) 게임 진행 버튼 / 플레이어 턴 컨트롤
    if st.session_state.mg_stage == "IDLE":
        col_next, col_reset = st.columns([3, 1])
        with col_next:
            if st.button("🃏 다음 핸드 진행하기", key="btn_next_hand", use_container_width=True):
                start_new_hand()
                st.rerun()
        with col_reset:
            if st.button("🔄 전체 새로 시작", key="btn_reset_all", use_container_width=True):
                reset_entire_tournament()
                start_new_hand()
                st.rerun()
    else:
        call_needed = max(0, st.session_state.mg_current_max_bet - st.session_state.mg_user_bet)
        min_raise_amt = call_needed + bb_setting
        max_raise_amt = st.session_state.mg_user_chips
        
        act_col1, act_col2, act_col3 = st.columns(3 if is_mobile else [1.2, 2, 1])

        # Check / Call
        if call_needed == 0:
            if act_col1.button("✅ 체크", use_container_width=True):
                add_player_action("Hero", "CHECK", "Check")
                st.session_state.mg_acted_players.append(0)
                st.session_state.mg_active_turn = get_next_turn(0)
                run_poker_turn_engine()
                st.rerun()
        else:
            actual_call = min(call_needed, st.session_state.mg_user_chips)
            if act_col1.button(f"📞 콜 ({actual_call} 칩)", use_container_width=True):
                st.session_state.mg_user_chips -= actual_call
                st.session_state.mg_pot += actual_call
                st.session_state.mg_user_bet += actual_call
                st.session_state.mg_user_total_contrib += actual_call
                add_player_action("Hero", "CALL", f"Call {actual_call}")
                st.session_state.mg_acted_players.append(0)
                st.session_state.mg_active_turn = get_next_turn(0)
                run_poker_turn_engine()
                st.rerun()

        # Raise (요청된 1. 버튼 -> 2. 수량 입력 -> 3. 설명 순 배치)
        with act_col2:
            if min_raise_amt <= max_raise_amt:
                raise_key = f"raise_input_val_{is_mobile}"
                raw_input_val = st.session_state.get(raise_key, min_raise_amt)
                custom_raise_val = max(min_raise_amt, min(raw_input_val, max_raise_amt))
                
                # 1. 최상단: 레이즈 버튼
                if st.button(f"🔺 레이즈 ({custom_raise_val} 칩)", use_container_width=True):
                    st.session_state.mg_user_chips -= custom_raise_val
                    st.session_state.mg_pot += custom_raise_val
                    st.session_state.mg_user_bet += custom_raise_val
                    st.session_state.mg_user_total_contrib += custom_raise_val
                    st.session_state.mg_current_max_bet = max(st.session_state.mg_current_max_bet, st.session_state.mg_user_bet)
                    add_player_action("Hero", "RAISE", f"Raise +{custom_raise_val}")
                    st.session_state.mg_acted_players = [0]
                    st.session_state.mg_active_turn = get_next_turn(0)
                    run_poker_turn_engine()
                    st.rerun()

                # 2. 그 아래: 레이즈 칩 수 입력
                st.number_input(
                    "레이즈 금액",
                    min_value=int(min_raise_amt),
                    max_value=int(max_raise_amt),
                    value=int(custom_raise_val),
                    step=int(bb_setting),
                    key=raise_key,
                    label_visibility="collapsed"
                )

                # 3. 최하단: 레이즈 가능 칩 범위 설명
                st.caption(f"최소 {min_raise_amt} ~ 최대 {max_raise_amt} 칩")
            else:
                if st.button(f"🔥 올인 ({st.session_state.mg_user_chips} 칩)", use_container_width=True):
                    allin = st.session_state.mg_user_chips
                    st.session_state.mg_pot += allin
                    st.session_state.mg_user_bet += allin
                    st.session_state.mg_user_total_contrib += allin
                    st.session_state.mg_user_chips = 0
                    st.session_state.mg_current_max_bet = max(st.session_state.mg_current_max_bet, st.session_state.mg_user_bet)
                    add_player_action("Hero", "RAISE", f"All-In {allin}")
                    st.session_state.mg_acted_players = [0]
                    st.session_state.mg_active_turn = get_next_turn(0)
                    run_poker_turn_engine()
                    st.rerun()

        # Fold
        if act_col3.button("🏳️ 폴드", use_container_width=True):
            st.session_state.mg_user_folded = True
            add_player_action("Hero", "FOLD", "Fold")
            st.session_state.mg_acted_players.append(0)
            st.session_state.mg_active_turn = get_next_turn(0)
            run_poker_turn_engine()
            st.rerun()
