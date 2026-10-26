```python
import random
from itertools import combinations

import streamlit as st
from treys import Card, Deck, Evaluator

st.set_page_config(
    page_title="홀덤 핸드·액션 어드바이저",
    page_icon="♠️",
    layout="wide",
)

RANKS = "AKQJT98765432"
SUITS = "shdc"

SUIT_SYMBOL = {
    "s": "♠",
    "h": "♥",
    "d": "♦",
    "c": "♣",
}

EVALUATOR = Evaluator()


# =========================================================
# 카드 및 핸드 유틸리티
# =========================================================

def card_label(card_code):
    """As -> A♠ 형식으로 표시"""
    return card_code[0] + SUIT_SYMBOL[card_code[1]]


def hand_type(row_rank, col_rank):
    """169개 시작 핸드 조합의 이름 생성"""
    if row_rank == col_rank:
        return row_rank + col_rank

    if RANKS.index(row_rank) < RANKS.index(col_rank):
        return row_rank + col_rank + "s"

    return col_rank + row_rank + "o"


def get_hand_combinations(hand):
    """핸드 유형에 해당하는 실제 카드 조합 생성"""
    if len(hand) == 2:
        rank = hand[0]
        return list(
            combinations(
                [rank + suit for suit in SUITS],
                2,
            )
        )

    rank1 = hand[0]
    rank2 = hand[1]
    suited_type = hand[2]

    if suited_type == "s":
        return [
            (rank1 + suit, rank2 + suit)
            for suit in SUITS
        ]

    return [
        (rank1 + suit1, rank2 + suit2)
        for suit1 in SUITS
        for suit2 in SUITS
        if suit1 != suit2
    ]


def estimate_equity(hero_cards, board_cards, opponents, iterations=2500):
    """
    상대의 비공개 핸드를 무작위로 가정한 몬테카를로 승률 추정.
    동률이면 팟 지분을 나누어 계산한다.
    """
    if len(hero_cards) != 2:
        raise ValueError("내 핸드는 정확히 2장이어야 합니다.")

    if len(board_cards) not in (0, 3, 4, 5):
        raise ValueError("보드는 0장, 3장, 4장 또는 5장이어야 합니다.")

    known_cards = hero_cards + board_cards

    if len(set(known_cards)) != len(known_cards):
        raise ValueError("내 핸드와 보드에 중복 카드가 있습니다.")

    if len(known_cards) + opponents * 2 > 52:
        raise ValueError("플레이어 수가 너무 많습니다.")

    deck = [
        card
        for card in Deck.GetFullDeck()
        if card not in known_cards
    ]

    missing_board = 5 - len(board_cards)
    total_share = 0.0

    for _ in range(iterations):
        draw_count = missing_board + opponents * 2
        drawn = random.sample(deck, draw_count)

        final_board = list(board_cards)
        final_board.extend(drawn[:missing_board])

        offset = missing_board

        hero_score = EVALUATOR.evaluate(
            final_board,
            hero_cards,
        )

        scores = [hero_score]

        for _opponent in range(opponents):
            opponent_cards = drawn[offset:offset + 2]
            offset += 2

            score = EVALUATOR.evaluate(
                final_board,
                opponent_cards,
            )

            scores.append(score)

        best_score = min(scores)

        if hero_score == best_score:
            winner_count = sum(
                1 for score in scores
                if score == best_score
            )

            total_share += 1 / winner_count

    return total_share / iterations


def get_recommendation(
    equity,
    pot,
    call_amount,
    remaining_stack,
):
    """
    팟 오즈와 추정 지분을 이용한 단순 참고용 액션 추천.
    전문 GTO 솔버가 아니다.
    """
    pot = max(0.0, float(pot))
    call_amount = max(0.0, float(call_amount))
    remaining_stack = max(0.0, float(remaining_stack))

    if pot + call_amount > 0:
        pot_odds = call_amount / (pot + call_amount)
    else:
        pot_odds = 0.0

    if remaining_stack <= 0:
        return (
            "폴드",
            "남은 시드가 없어 추가 베팅할 수 없습니다.",
            pot_odds,
        )

    if call_amount <= 0:
        if equity >= 0.65:
            return (
                "베팅/올인 검토",
                "추정 지분이 높은 편입니다. 상대 범위와 스택을 함께 고려하세요.",
                pot_odds,
            )

        return (
            "체크 권장",
            "추가 콜 금액이 없습니다. 체크할 수 있는 상황인지 확인하세요.",
            pot_odds,
        )

    if call_amount >= remaining_stack:
        if equity >= max(0.58, pot_odds + 0.08):
            return (
                "올인 콜 검토",
                "콜 금액이 남은 시드에 가깝거나 더 큽니다.",
                pot_odds,
            )

        return (
            "폴드 권장",
            "현재 추정 지분으로는 큰 금액을 콜하기 어렵습니다.",
            pot_odds,
        )

    if equity >= pot_odds + 0.12:
        return (
            "콜 검토",
            "팟 오즈 대비 추정 지분이 충분한 편입니다.",
            pot_odds,
        )

    if equity >= pot_odds + 0.03:
        return (
            "콜 또는 폴드",
            "팟 오즈와 추정 지분의 차이가 작습니다.",
            pot_odds,
        )

    return (
        "폴드 권장",
        "현재 입력 기준으로 콜에 필요한 지분을 충족하지 못합니다.",
        pot_odds,
    )


# =========================================================
# 게임 상태 관리
# =========================================================

def init_state():
    defaults = {
        "initial_stack": 10000.0,
        "remaining_stack": 10000.0,

        "bb": 100.0,
        "sb": 50.0,
        "ante": 0.0,

        "player_seat": 6,
        "opponent_seats": [1, 3, 8],
        "start_seat": 1,

        "selected_hand": "AKs",
        "selected_combo": "As|Ks",

        "board_codes": [],

        "pre_pot": 150.0,
        "pre_call": 100.0,

        "flop_pot": 150.0,
        "flop_call": 100.0,

        "hand_started": False,
        "hand_finished": False,
        "hand_number": 1,

        "ante_paid_hand": False,
        "last_action": "",
        "last_notice": "",

        "equity": None,
        "equity_stage": None,

        "pre_iterations": 2500,
        "post_iterations": 2500,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def on_bb_change():
    """BB 변경 시 SB 및 기본 콜 금액을 갱신"""
    bb = float(st.session_state["bb"])

    st.session_state["sb"] = bb / 2
    st.session_state["pre_call"] = bb
    st.session_state["flop_call"] = bb

    if not st.session_state["hand_started"]:
        opponents = len(st.session_state["opponent_seats"])
        total_players = opponents + 1

        estimated_pot = (
            bb
            + bb / 2
            + total_players * float(st.session_state["ante"])
        )

        st.session_state["pre_pot"] = estimated_pot
        st.session_state["flop_pot"] = estimated_pot


def on_initial_stack_change():
    """초기 시드를 수정하면 현재 시드도 새 값으로 맞춤"""
    st.session_state["remaining_stack"] = float(
        st.session_state["initial_stack"]
    )


def reset_blinds():
    """
    블라인드·앤티 초기화.
    초기 시드와 현재 남은 시드는 유지한다.
    """
    st.session_state["bb"] = 100.0
    st.session_state["sb"] = 50.0
    st.session_state["ante"] = 0.0

    st.session_state["pre_call"] = 100.0
    st.session_state["flop_call"] = 100.0

    if not st.session_state["hand_started"]:
        st.session_state["pre_pot"] = 150.0
        st.session_state["flop_pot"] = 150.0

    st.session_state["equity"] = None
    st.session_state["equity_stage"] = None


def reset_game():
    """게임 전체 초기화"""
    defaults = {
        "initial_stack": 10000.0,
        "remaining_stack": 10000.0,

        "bb": 100.0,
        "sb": 50.0,
        "ante": 0.0,

        "player_seat": 6,
        "opponent_seats": [1, 3, 8],
        "start_seat": 1,

        "selected_hand": "AKs",
        "selected_combo": "As|Ks",

        "board_codes": [],

        "pre_pot": 150.0,
        "pre_call": 100.0,

        "flop_pot": 150.0,
        "flop_call": 100.0,

        "hand_started": False,
        "hand_finished": False,
        "hand_number": 1,

        "ante_paid_hand": False,
        "last_action": "",
        "last_notice": "",

        "equity": None,
        "equity_stage": None,

        "pre_iterations": 2500,
        "post_iterations": 2500,
    }

    for key, value in defaults.items():
        st.session_state[key] = value


def move_start_seat():
    """시작 플레이어를 다음 좌석으로 이동"""
    st.session_state["start_seat"] = (
        int(st.session_state["start_seat"]) % 10
    ) + 1


def finish_hand(reason):
    """
    핸드를 종료한다.
    다음 핸드 시작 좌석으로 이동하지만 남은 시드는 유지한다.
    """
    if st.session_state["hand_finished"]:
        return

    st.session_state["hand_finished"] = True
    st.session_state["hand_started"] = False
    st.session_state["last_action"] = reason

    move_start_seat()

    st.session_state["equity"] = None
    st.session_state["equity_stage"] = None

    st.session_state["board_codes"] = []

    st.session_state["last_notice"] = (
        f"{reason} 처리 완료. "
        f"다음 핸드 시작 플레이어는 "
        f"{st.session_state['start_seat']}번입니다. "
        f"현재 남은 시드는 "
        f"{st.session_state['remaining_stack']:,.0f}입니다."
    )


def start_hand():
    """
    다음 핸드를 시작한다.
    앤티를 아직 내지 않았다면 내 시드에서 차감하고 팟에 더한다.
    """
    if st.session_state["remaining_stack"] <= 0:
        st.session_state["last_notice"] = (
            "남은 시드가 없어 새 핸드를 시작할 수 없습니다."
        )
        return

    if st.session_state["hand_started"]:
        st.session_state["last_notice"] = (
            "이미 핸드가 진행 중입니다."
        )
        return

    st.session_state["hand_started"] = True
    st.session_state["hand_finished"] = False
    st.session_state["ante_paid_hand"] = False

    st.session_state["equity"] = None
    st.session_state["equity_stage"] = None
    st.session_state["board_codes"] = []

    opponents = len(st.session_state["opponent_seats"])
    total_players = opponents + 1

    # 핸드 시작 시 새 팟을 구성한다.
    st.session_state["pre_pot"] = (
        st.session_state["sb"]
        + st.session_state["bb"]
        + total_players * st.session_state["ante"]
    )

    st.session_state["flop_pot"] = st.session_state["pre_pot"]

    # 내가 시작 플레이어 다음 차례인 경우에도 앤티는 핸드 시작 시 차감한다.
    ante = float(st.session_state["ante"])
    paid_ante = min(
        ante,
        float(st.session_state["remaining_stack"]),
    )

    st.session_state["remaining_stack"] -= paid_ante
    st.session_state["pre_pot"] += paid_ante
    st.session_state["flop_pot"] = st.session_state["pre_pot"]

    st.session_state["ante_paid_hand"] = True

    st.session_state["last_notice"] = (
        f"핸드 {st.session_state['hand_number']} 시작. "
        f"앤티 {paid_ante:,.0f} 차감, "
        f"남은 시드 {st.session_state['remaining_stack']:,.0f}."
    )

    st.session_state["hand_number"] += 1


def apply_call(stage):
    """콜 금액만큼 시드에서 차감하고 팟에 더한다."""
    if not st.session_state["hand_started"]:
        st.session_state["last_notice"] = (
            "먼저 '새 핸드 시작' 버튼을 눌러주세요."
        )
        return

    if st.session_state["hand_finished"]:
        return

    call_key = "pre_call" if stage == "pre" else "flop_call"
    pot_key = "pre_pot" if stage == "pre" else "flop_pot"

    requested = max(
        0.0,
        float(st.session_state[call_key]),
    )

    remaining = max(
        0.0,
        float(st.session_state["remaining_stack"]),
    )

    paid = min(requested, remaining)

    st.session_state["remaining_stack"] = remaining - paid
    st.session_state[pot_key] += paid

    # 콜을 한 번 처리한 뒤 같은 금액이 중복 차감되지 않도록 초기화한다.
    st.session_state[call_key] = 0.0

    if stage == "pre":
        st.session_state["flop_pot"] = st.session_state["pre_pot"]

    st.session_state["last_notice"] = (
        f"{stage.upper()} 콜 처리: {paid:,.0f} 투입. "
        f"남은 시드 {st.session_state['remaining_stack']:,.0f}, "
        f"현재 팟 {st.session_state[pot_key]:,.0f}."
    )

    st.session_state["equity"] = None
    st.session_state["equity_stage"] = None

    if st.session_state["remaining_stack"] <= 0:
        st.session_state["last_notice"] += (
            " 남은 시드가 0이므로 올인 상태입니다."
        )


def apply_fold():
    """폴드 시 핸드를 종료하고 다음 핸드 준비 상태로 이동"""
    finish_hand("폴드")


# =========================================================
# 초기화
# =========================================================

init_state()


# =========================================================
# 사이드바: 게임 설정
# =========================================================

with st.sidebar:
    st.header("게임 설정")

    st.number_input(
        "초기 시드 / 시작 스택",
        min_value=1.0,
        step=100.0,
        key="initial_stack",
        on_change=on_initial_stack_change,
    )

    st.metric(
        "현재 남은 시드",
        f"{st.session_state['remaining_stack']:,.0f}",
    )

    st.number_input(
        "빅블라인드(BB)",
        min_value=1.0,
        step=10.0,
        key="bb",
        on_change=on_bb_change,
    )

    st.number_input(
        "스몰블라인드(SB = BB ÷ 2)",
        min_value=0.5,
        step=5.0,
        key="sb",
        disabled=True,
    )

    st.number_input(
        "앤티(Ante / ENT)",
        min_value=0.0,
        step=5.0,
        key="ante",
    )

    col1, col2 = st.columns(2)

    with col1:
        st.button(
            "블라인드·앤티 초기화",
            use_container_width=True,
            on_click=reset_blinds,
        )

    with col2:
        st.button(
            "게임 전체 초기화",
            type="primary",
            use_container_width=True,
            on_click=reset_game,
        )

    with st.expander("용어 설명", expanded=True):
        st.markdown("""
        - **초기 시드:** 게임을 시작할 때 보유한 칩.
        - **현재 남은 시드:** 앤티와 콜 등으로 칩을 낸 뒤 남은 금액.
        - **SB:** 스몰 블라인드. 이 앱에서는 BB의 절반.
        - **BB:** 빅 블라인드. 기본 콜 금액의 기준값.
        - **앤티(ENT):** 핸드마다 내는 강제 베팅.
        - **현재 팟:** 중앙에 모인 칩의 총액.
        - **콜 필요 금액:** 현재 베팅에 맞추기 위해 추가로 낼 금액.
        - **팟 오즈:** 콜 금액 대비 최종 팟을 기준으로 계산한 손익분기 승률 근사치.
        """)


# =========================================================
# 메인 화면
# =========================================================

st.title("♠️ 홀덤 핸드·액션 어드바이저")

st.caption(
    "승률은 상대의 실제 핸드 범위를 알 수 없다고 가정한 "
    "무작위 시뮬레이션 결과입니다. 추천은 참고용입니다."
)

st.subheader("1. 게임 진행")

status_col1, status_col2, status_col3 = st.columns(3)

status_col1.metric(
    "핸드 번호",
    st.session_state["hand_number"],
)

status_col2.metric(
    "시작 플레이어",
    f"{st.session_state['start_seat']}번",
)

status_col3.metric(
    "현재 상태",
    "진행 중" if st.session_state["hand_started"]
    else "종료 / 대기",
)

game_buttons = st.columns(3)

with game_buttons[0]:
    if st.button(
        "새 핸드 시작",
        type="primary",
        use_container_width=True,
        disabled=st.session_state["hand_started"],
    ):
        start_hand()
        st.rerun()

with game_buttons[1]:
    if st.button(
        "게임 종료",
        use_container_width=True,
        disabled=not st.session_state["hand_started"],
    ):
        finish_hand("게임 종료")
        st.rerun()

with game_buttons[2]:
    if st.button(
        "폴드",
        use_container_width=True,
        disabled=not st.session_state["hand_started"],
    ):
        apply_fold()
        st.rerun()

if st.session_state["last_notice"]:
    st.info(st.session_state["last_notice"])

st.caption(
    "핸드 종료 후 시작 플레이어가 1→2→…→10→1 순서로 이동합니다. "
    "핸드 종료 시 남은 시드는 유지됩니다."
)


# =========================================================
# 좌석 지정
# =========================================================

st.subheader("2. 테이블 자리 지정")

seat_cols = st.columns(5)

for seat in range(1, 11):
    col = seat_cols[(seat - 1) % 5]

    if seat == st.session_state["player_seat"]:
        label = f"🟢 {seat}번 · 나"
    elif seat in st.session_state["opponent_seats"]:
        label = f"🔵 {seat}번 · 플레이어"
    elif seat == st.session_state["start_seat"]:
        label = f"⭐ {seat}번 · 시작"
    else:
        label = f"⚪ {seat}번 · 빈자리"

    col.markdown(
        f"""
        <div style="
            border:1px solid #888;
            border-radius:10px;
            padding:10px;
            text-align:center;
            margin-bottom:5px;">
            {label}
        </div>
        """,
        unsafe_allow_html=True,
    )

seat1, seat2, seat3 = st.columns(3)

with seat1:
    st.selectbox(
        "내 자리",
        list(range(1, 11)),
        key="player_seat",
    )

with seat2:
    possible_opponents = [
        seat for seat in range(1, 11)
        if seat != st.session_state["player_seat"]
    ]

    st.multiselect(
        "나 이외의 플레이어 자리",
        possible_opponents,
        key="opponent_seats",
    )

with seat3:
    st.selectbox(
        "시작 플레이어 자리",
        list(range(1, 11)),
        key="start_seat",
    )

opponents = max(1, len(st.session_state["opponent_seats"]))

st.caption(
    f"승률 계산 인원: 나 포함 "
    f"{len(st.session_state['opponent_seats']) + 1}명"
)


# =========================================================
# 핸드 조합표
# =========================================================

st.subheader("3. 내 핸드 선택 — 169개 조합표")

st.markdown(
    "🟦 페어 · 🟩 수딧(같은 무늬) · "
    "🟧 오프수딧(다른 무늬) · 🟥 선택된 핸드"
)

header = st.columns([0.6] + [1] * 13)
header[0].markdown("**행/열**")

for j, rank in enumerate(RANKS):
    header[j + 1].markdown(f"**{rank}**")

for i, row_rank in enumerate(RANKS):
    cols = st.columns([0.6] + [1] * 13)
    cols[0].markdown(f"**{row_rank}**")

    for j, col_rank in enumerate(RANKS):
        hand = hand_type(row_rank, col_rank)

        if hand == st.session_state["selected_hand"]:
            prefix = "🟥"
        elif len(hand) == 2:
            prefix = "🟦"
        elif hand.endswith("s"):
            prefix = "🟩"
        else:
            prefix = "🟧"

        if cols[j + 1].button(
            f"{prefix} {hand}",
            key=f"hand_{i}_{j}",
            use_container_width=True,
        ):
            st.session_state["selected_hand"] = hand
            st.session_state["equity"] = None
            st.session_state["equity_stage"] = None
            st.rerun()

with st.expander("시작 핸드 강도 설명", expanded=True):
    st.markdown("""
    **프리플랍 핸드 강도는 대략적인 기준입니다.**
    실제 강도는 상대 수, 포지션, 스택과 베팅에 따라 달라집니다.

    1. **최상위 페어:** AA, KK, QQ, JJ
    2. **강한 상위 카드:** AKs, AKo, AQs
    3. **중상위 핸드:** TT~77, AJs, KQs, KJs, QJs
    4. **중간 페어·수딧 연결 핸드:** 66~22, JTs, T9s, 98s
    5. **약한 오프수딧 핸드:** 낮은 비연결 카드 조합

    - **페어:** 같은 숫자의 카드 두 장
    - **수딧(s):** 두 카드의 무늬가 같음
    - **오프수딧(o):** 두 카드의 무늬가 다름
    - 169개 시작 핸드 유형은 실제 카드 조합 1,326개를 대표합니다.
    """)

selected_hand = st.session_state["selected_hand"]
hand_combos = get_hand_combinations(selected_hand)

combo_labels = [
    f"{card_label(a)}  {card_label(b)}"
    for a, b in hand_combos
]

combo_codes = [
    f"{a}|{b}"
    for a, b in hand_combos
]

combo_map = dict(zip(combo_labels, combo_codes))

current_code = st.session_state["selected_combo"]

current_label = next(
    (
        label for label, code in combo_map.items()
        if code == current_code
    ),
    combo_labels[0],
)

selected_label = st.selectbox(
    "실제 카드 무늬 선택",
    combo_labels,
    index=combo_labels.index(current_label),
)

st.session_state["selected_combo"] = combo_map[selected_label]

hero_codes = st.session_state["selected_combo"].split("|")
hero_cards = [Card.new(code) for code in hero_codes]

st.write(
    f"선택 핸드: **{selected_hand}** · "
    f"실제 카드: **{card_label(hero_codes[0])}, "
    f"{card_label(hero_codes[1])}**"
)


# =========================================================
# 프리플랍
# =========================================================

st.subheader("4. 프리플랍 승률 및 액션 추천")

pre1, pre2, pre3 = st.columns(3)

with pre1:
    st.number_input(
        "3. 현재 팟 금액",
        min_value=0.0,
        step=10.0,
        key="pre_pot",
    )

with pre2:
    st.number_input(
        "3. 콜 필요 금액",
        min_value=0.0,
        step=10.0,
        key="pre_call",
    )

with pre3:
    st.select_slider(
        "시뮬레이션 반복 횟수",
        options=[500, 1000, 2500, 5000, 10000],
        key="pre_iterations",
    )

pre_buttons = st.columns(3)

with pre_buttons[0]:
    if st.button(
        "3. 콜",
        use_container_width=True,
        disabled=not st.session_state["hand_started"],
    ):
        apply_call("pre")
        st.rerun()

with pre_buttons[1]:
    if st.button(
        "3. 폴드",
        use_container_width=True,
        disabled=not st.session_state["hand_started"],
    ):
        apply_fold()
        st.rerun()

with pre_buttons[2]:
    if st.button(
        "프리플랍 승률 계산",
        type="primary",
        use_container_width=True,
    ):
        try:
            with st.spinner("승률 계산 중..."):
                equity = estimate_equity(
                    hero_cards,
                    [],
                    opponents,
                    int(st.session_state["pre_iterations"]),
                )

            st.session_state["equity"] = equity
            st.session_state["equity_stage"] = "pre"

        except Exception as exc:
            st.error(str(exc))

if (
    st.session_state["equity"] is not None
    and st.session_state["equity_stage"] == "pre"
):
    equity = st.session_state["equity"]

    action, reason, pot_odds = get_recommendation(
        equity,
        st.session_state["pre_pot"],
        st.session_state["pre_call"],
        st.session_state["remaining_stack"],
    )

    c1, c2, c3 = st.columns(3)

    c1.metric("추정 승률", f"{equity * 100:.1f}%")
    c2.metric("콜 필요 승률", f"{pot_odds * 100:.1f}%")
    c3.metric("추천 액션", action)

    st.info(reason)


# =========================================================
# 플랍 / 턴 / 리버
# =========================================================

st.subheader("5. 플랍·턴·리버 승률 및 액션 추천")

all_card_codes = [
    rank + suit
    for rank in "23456789TJQKA"
    for suit in SUITS
]

used_hero = set(hero_codes)

available_board = [
    code for code in all_card_codes
    if code not in used_hero
]

board_label_map = {
    card_label(code): code
    for code in available_board
}

board_options = ["(선택 안 함)"] + list(board_label_map.keys())

board_cols = st.columns(5)
selected_board = []

for i in range(5):
    with board_cols[i]:
        current_codes = st.session_state["board_codes"]

        current_code = (
            current_codes[i]
            if i < len(current_codes)
            else None
        )

        current_label = next(
            (
                label for label, code in board_label_map.items()
                if code == current_code
            ),
            "(선택 안 함)",
        )

        label = st.selectbox(
            f"보드 카드 {i + 1}",
            board_options,
            index=board_options.index(current_label),
            key=f"board_select_{i}",
        )

        if label != "(선택 안 함)":
            selected_board.append(board_label_map[label])

st.session_state["board_codes"] = selected_board

if len(selected_board) not in (0, 3, 4, 5):
    st.warning(
        "보드는 0장, 3장(플랍), 4장(턴), "
        "5장(리버)으로 입력하세요."
    )

if len(set(selected_board)) != len(selected_board):
    st.error("보드 카드가 중복되었습니다.")

flop1, flop2, flop3 = st.columns(3)

with flop1:
    st.number_input(
        "4. 현재 팟 금액",
        min_value=0.0,
        step=10.0,
        key="flop_pot",
    )

with flop2:
    st.number_input(
        "4. 콜 필요 금액",
        min_value=0.0,
        step=10.0,
        key="flop_call",
    )

with flop3:
    st.select_slider(
        "시뮬레이션 반복 횟수",
        options=[500, 1000, 2500, 5000, 10000],
        key="post_iterations",
    )

flop_buttons = st.columns(3)

with flop_buttons[0]:
    if st.button(
        "4. 콜",
        use_container_width=True,
        disabled=not st.session_state["hand_started"],
    ):
        apply_call("flop")
        st.rerun()

with flop_buttons[1]:
    if st.button(
        "4. 폴드",
        use_container_width=True,
        disabled=not st.session_state["hand_started"],
    ):
        apply_fold()
        st.rerun()

with flop_buttons[2]:
    if st.button(
        "보드 기준 승률 계산",
        type="primary",
        use_container_width=True,
    ):
        if len(selected_board) not in (3, 4, 5):
            st.error(
                "플랍은 3장, 턴은 4장, 리버는 5장을 입력하세요."
            )

        elif len(set(selected_board)) != len(selected_board):
            st.error("중복된 보드 카드가 있습니다.")

        elif set(selected_board) & used_hero:
            st.error("내 핸드와 보드에 중복 카드가 있습니다.")

        else:
            try:
                board_cards = [
                    Card.new(code)
                    for code in selected_board
                ]

                with st.spinner("보드 기준 승률 계산 중..."):
                    equity = estimate_equity(
                        hero_cards,
                        board_cards,
                        opponents,
                        int(st.session_state["post_iterations"]),
                    )

                st.session_state["equity"] = equity
                st.session_state["equity_stage"] = "post"

            except Exception as exc:
                st.error(str(exc))

if (
    st.session_state["equity"] is not None
    and st.session_state["equity_stage"] == "post"
):
    equity = st.session_state["equity"]

    action, reason, pot_odds = get_recommendation(
        equity,
        st.session_state["flop_pot"],
        st.session_state["flop_call"],
        st.session_state["remaining_stack"],
    )

    c1, c2, c3 = st.columns(3)

    c1.metric("보드 기준 추정 승률", f"{equity * 100:.1f}%")
    c2.metric("콜 필요 승률", f"{pot_odds * 100:.1f}%")
    c3.metric("추천 액션", action)

    st.info(reason)


# =========================================================
# 안내
# =========================================================

with st.expander("승률 계산 및 게임 상태 처리 안내"):
    st.markdown("""
    - 승률은 상대의 비공개 핸드를 무작위로 가정한 시뮬레이션 결과입니다.
    - 핸드 시작 시 앤티를 내 시드에서 차감하고 팟에 더합니다.
    - 콜 버튼은 입력된 콜 금액만큼 시드에서 차감하고 팟에 더합니다.
    - 콜 처리 후 콜 금액 입력값은 0으로 초기화되어 중복 차감을 방지합니다.
    - 게임 종료 또는 폴드 시 시작 플레이어가 다음 좌석으로 이동합니다.
    - 핸드 종료 시 남은 시드는 유지됩니다.
    - 게임 전체 초기화 버튼을 누르면 시드와 게임 설정이 초기화됩니다.
    - 이 앱은 실제 온라인 포커 테이블에 연결되지 않습니다.
    - 액션 추천은 참고용이며 승리나 수익을 보장하지 않습니다.
    """)
```
