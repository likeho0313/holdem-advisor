import random
from itertools import combinations

import pandas as pd
import streamlit as st
from treys import Card, Deck, Evaluator

st.set_page_config(page_title="홀덤 프리플랍·플랍 어드바이저", page_icon="♠️", layout="wide")

RANKS = "AKQJT98765432"
SUITS = {"♠ 스페이드": "s", "♥ 하트": "h", "♦ 다이아": "d", "♣ 클럽": "c"}
SUIT_LABELS = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
EVAL = Evaluator()


def card_text(card):
    return Card.int_to_str(card)[0] + SUIT_LABELS[Card.int_to_str(card)[1]]


def hand_types():
    result = []
    for i, r1 in enumerate(RANKS):
        for j, r2 in enumerate(RANKS):
            if i == j:
                result.append((r1 + r2, r1 + r2, "페어"))
            elif i < j:
                result.append((r1 + r2 + "s", r1 + r2 + "s", "수딧"))
            else:
                result.append((r2 + r1 + "o", r2 + r1 + "o", "오프수딧"))
    # Matrix order is row rank x column rank, with suited above diagonal and offsuit below.
    return result


def matrix_hand(row_rank, col_rank):
    if row_rank == col_rank:
        return row_rank + col_rank
    if RANKS.index(row_rank) < RANKS.index(col_rank):
        return row_rank + col_rank + "s"
    return col_rank + row_rank + "o"


def combos_for_hand(hand):
    if len(hand) == 2:
        rank = hand[0]
        combos = []
        cards = [rank + s for s in "shdc"]
        for a, b in combinations(cards, 2):
            combos.append((a, b))
        return combos
    r1, r2, kind = hand[0], hand[1], hand[2]
    combos = []
    if kind == "s":
        for s in "shdc":
            combos.append((r1 + s, r2 + s))
    else:
        for s1 in "shdc":
            for s2 in "shdc":
                if s1 != s2:
                    combos.append((r1 + s1, r2 + s2))
    return combos


def parse_card(code):
    return Card.new(code)


def equity_sim(hero, board, opponents, iterations=2500):
    """Monte Carlo equity against random unknown opponent cards."""
    if len(hero) != 2 or len(board) > 5:
        return 0.0
    known = list(hero) + list(board)
    if len(set(known)) != len(known):
        raise ValueError("내 핸드와 보드 카드가 중복됩니다.")
    if len(hero) + len(board) + opponents * 2 > 52:
        raise ValueError("플레이어 수가 너무 많습니다.")
    deck = [c for c in Deck.GetFullDeck() if c not in known]
    wins = ties = 0.0
    needed_board = 5 - len(board)
    for _ in range(iterations):
        draw = random.sample(deck, needed_board + opponents * 2)
        runout = list(board) + draw[:needed_board]
        offset = needed_board
        hero_score = EVAL.evaluate(runout, list(hero))
        scores = [hero_score]
        for _opp in range(opponents):
            hole = draw[offset:offset + 2]
            offset += 2
            scores.append(EVAL.evaluate(runout, hole))
        best = min(scores)
        if hero_score == best:
            winners = sum(1 for x in scores if x == best)
            if winners == 1:
                wins += 1
            else:
                ties += 1 / winners
    return (wins + ties) / iterations


def recommendation(equity, pot, to_call, stack, stage, players):
    pot = max(0.0, float(pot))
    to_call = max(0.0, float(to_call))
    stack = max(0.0, float(stack))
    pot_odds = to_call / (pot + to_call) if (pot + to_call) > 0 else 0.0
    if stack <= 0:
        return "폴드", "남은 스택이 없어 추가 액션을 할 수 없습니다.", pot_odds
    if to_call >= stack and stack > 0:
        if equity >= 0.58:
            return "올인 검토", "콜 금액이 스택에 가까우며 추정 지분이 높습니다. 상대 핸드 범위에 따라 달라집니다.", pot_odds
        if equity >= pot_odds + 0.08:
            return "콜 검토", "팟 오즈보다 추정 지분이 높지만, 올인 콜은 변동성이 큽니다.", pot_odds
        return "폴드 권장", "필요 지분에 비해 추정 지분이 낮습니다.", pot_odds
    if to_call == 0:
        if equity >= (0.62 if stage == "프리플랍" else 0.68):
            return "베팅/올인 검토", "체크 가능한 상황이라도 강한 지분입니다. 체크·베팅 선택은 상대 성향과 보드에 좌우됩니다.", pot_odds
        return "체크 권장", "무료로 다음 카드를 볼 수 있다면 체크가 기본 선택입니다.", pot_odds
    if equity >= pot_odds + 0.12 and equity >= 0.48:
        return "콜 검토", "팟 오즈 대비 충분한 지분으로 추정됩니다. 레이즈/올인 여부는 스택과 상대 범위를 추가로 고려하세요.", pot_odds
    if equity >= pot_odds + 0.03:
        return "콜 또는 폴드", "팟 오즈와 추정 지분 차이가 작아 상대 베팅 크기·포지션·상대 범위가 중요합니다.", pot_odds
    return "폴드 권장", "현재 입력 기준으로는 콜에 필요한 지분을 충족하지 못합니다.", pot_odds


def reset_blinds():
    # Keep the user's initial stack and table/hand settings intact.
    st.session_state["bb"] = 100
    st.session_state["sb"] = 50
    st.session_state["ante"] = 0
    st.session_state["equity_result"] = None
    st.session_state["last_stage"] = None


def reset_game():
    # Reset all game inputs to their initial values.
    defaults = {
        "seed_stack": 10000, "bb": 100, "sb": 50, "ante": 0,
        "player_seat": 6, "opponent_seats": [1, 3, 8], "start_seat": 1,
        "selected_hand": "AKs", "selected_combo": "As|Ks",
        "flop_cards": [], "equity_result": None,
        "last_stage": None, "last_hand": None,
    }
    for key, value in defaults.items():
        st.session_state[key] = value


def init_state():
    defaults = {
        "seed_stack": 10000,
        "bb": 100,
        "sb": 50,
        "ante": 0,
        "player_seat": 6,
        "opponent_seats": [1, 3, 8],
        "start_seat": 1,
        "selected_hand": "AKs",
        "selected_combo": "As|Ks",
        "flop_cards": [],
        "pot_override": 0,
        "call_amount": 0,
        "equity_result": None,
        "last_stage": None,
        "last_hand": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_state()

st.title("♠️ 홀덤 핸드·액션 어드바이저")
st.caption("WPL 핸드레인지 차트의 169개 핸드 조합 개념을 참고한 개인용 분석 도구입니다. 실제 승률·액션은 상대 핸드 범위, 베팅 이력, 포지션 등에 따라 달라집니다.")

with st.sidebar:
    st.header("게임 설정")
    st.number_input("초기 시드 / 내 스택", min_value=1, step=100, key="seed_stack", help="블라인드·앤티 초기화 시에도 이 값은 유지됩니다.")
    st.number_input("빅블라인드(BB)", min_value=1, step=10, key="bb")
    # SB is always synchronized to half the BB. User can edit BB, but SB is automatic.
    st.session_state["sb"] = st.session_state["bb"] / 2
    st.number_input("스몰블라인드(SB, BB의 1/2 자동)", min_value=0.5, value=float(st.session_state["sb"]), step=5.0, disabled=True)
    st.number_input("앤티(Ante / ENT)", min_value=0, step=5, key="ante")
    c1, c2 = st.columns(2)
    with c1:
        st.button("블라인드·앤티 초기화", use_container_width=True, on_click=reset_blinds)
    with c2:
        st.button("게임 전체 초기화", type="primary", use_container_width=True, on_click=reset_game)
    st.info("블라인드·앤티 초기화는 기본값(BB 100 / SB 50 / 앤티 0)으로 되돌립니다. 초기 시드는 유지됩니다.")

st.subheader("1. 테이블 자리 지정")
seat_cols = st.columns(5)
for seat in range(1, 11):
    col = seat_cols[(seat - 1) % 5]
    if seat == st.session_state["player_seat"]:
        label = f"🟢 {seat}번 · 나"
    elif seat in st.session_state["opponent_seats"]:
        label = f"🔵 {seat}번 · 플레이어"
    else:
        label = f"⚪ {seat}번 · 빈자리"
    col.markdown(f"<div style='border:1px solid #888;border-radius:10px;padding:10px;text-align:center'>{label}</div>", unsafe_allow_html=True)

seat1, seat2, seat3 = st.columns(3)
with seat1:
    st.selectbox("내 자리", list(range(1, 11)), key="player_seat")
with seat2:
    possible_opponents = [s for s in range(1, 11) if s != st.session_state["player_seat"]]
    st.multiselect("나 이외의 플레이어 자리", possible_opponents, key="opponent_seats", help="선택한 자리의 상대는 카드가 공개되지 않은 무작위 핸드로 계산합니다.")
with seat3:
    st.selectbox("시작 플레이어 자리", list(range(1, 11)), key="start_seat")

opponents = len(st.session_state["opponent_seats"])
players_total = opponents + 1
st.caption(f"현재 계산 인원: 나 포함 {players_total}명 · 시작 플레이어: {st.session_state['start_seat']}번 · SB {st.session_state['sb']:,.1f} / BB {st.session_state['bb']:,.0f} / 앤티 {st.session_state['ante']:,.0f}")

st.subheader("2. 내 핸드 선택 — 169개 핸드 조합")
st.write("행·열의 랭크를 눌러 페어(AA), 수딧(AKs), 오프수딧(AKo) 중 하나를 선택하세요.")
rank_cols = st.columns([0.6] + [1] * 13)
rank_cols[0].markdown("**행/열**")
for j, rank in enumerate(RANKS):
    rank_cols[j + 1].markdown(f"**{rank}**")
for i, row_rank in enumerate(RANKS):
    cols = st.columns([0.6] + [1] * 13)
    cols[0].markdown(f"**{row_rank}**")
    for j, col_rank in enumerate(RANKS):
        hand = matrix_hand(row_rank, col_rank)
        selected = hand == st.session_state["selected_hand"]
        if len(hand) == 2:
            color = "#b8d9f5"
        elif hand.endswith("s"):
            color = "#c9e8cc"
        else:
            color = "#f6dfb8"
        if selected:
            color = "#ffb3b3"
        label = hand
        if cols[j + 1].button(label, key=f"hand_{i}_{j}", use_container_width=True, help={"AKs": "수딧", "AKo": "오프수딧"}.get(hand, hand)):
            st.session_state["selected_hand"] = hand
            st.session_state["equity_result"] = None
            st.rerun()
        # The button itself is the selection surface; color is shown in the legend below.
st.markdown("🟦 페어 · 🟩 수딧(같은 무늬) · 🟧 오프수딧(다른 무늬) · 🟥 현재 선택")

hand = st.session_state["selected_hand"]
combos = combos_for_hand(hand)
combo_labels = [f"{a[0]}{SUIT_LABELS[a[1]]}  {b[0]}{SUIT_LABELS[b[1]]}" for a, b in combos]
combo_to_code = {label: f"{a}|{b}" for label, (a, b) in zip(combo_labels, combos)}
current_code = st.session_state.get("selected_combo", "")
current_label = next((label for label, code in combo_to_code.items() if code == current_code), combo_labels[0])
selected_label = st.selectbox("실제 무늬 조합", combo_labels, index=combo_labels.index(current_label), help="플랍과 카드 무늬가 겹치지 않도록 실제 카드 조합을 선택합니다.")
st.session_state["selected_combo"] = combo_to_code[selected_label]
hero_codes = st.session_state["selected_combo"].split("|")
hero = [parse_card(c) for c in hero_codes]
st.write(f"**선택한 핸드:** {hand} · 실제 카드: {card_text(hero[0])}, {card_text(hero[1])}")

st.subheader("3. 프리플랍 승률 및 액션 추천")
pre1, pre2, pre3 = st.columns(3)
with pre1:
    pre_pot = st.number_input("현재 팟 금액(프리플랍)", min_value=0.0, value=float(st.session_state["sb"] + st.session_state["bb"] + players_total * st.session_state["ante"]), step=10.0, key="pre_pot")
with pre2:
    pre_call = st.number_input("콜에 필요한 금액", min_value=0.0, value=float(st.session_state["bb"]), step=10.0, key="pre_call")
with pre3:
    pre_iterations = st.select_slider("계산 정확도", options=[500, 1000, 2500, 5000, 10000], value=2500, key="pre_iterations")
if st.button("프리플랍 승률 계산", type="primary"):
    try:
        with st.spinner("몬테카를로 시뮬레이션 중..."):
            eq = equity_sim(hero, [], opponents, int(pre_iterations))
        st.session_state["equity_result"] = eq
        st.session_state["last_stage"] = "프리플랍"
        st.session_state["last_hand"] = hand
    except Exception as exc:
        st.error(str(exc))

if st.session_state.get("last_stage") == "프리플랍" and st.session_state.get("equity_result") is not None:
    eq = st.session_state["equity_result"]
    action, reason, pot_odds = recommendation(eq, pre_pot, pre_call, st.session_state["seed_stack"], "프리플랍", players_total)
    m1, m2, m3 = st.columns(3)
    m1.metric("추정 승률(지분)", f"{eq * 100:.1f}%")
    m2.metric("팟 오즈 기준", f"{pot_odds * 100:.1f}%")
    m3.metric("추천 액션", action)
    st.info(reason)

st.subheader("4. 플랍 입력 및 액션 추천")
all_card_codes = [r + s for r in "23456789TJQKA" for s in "shdc"]
used_hero = set(hero_codes)
available_board = [c for c in all_card_codes if c not in used_hero]
flop_options = ["(선택 안 함)"] + [f"{c[0]}{SUIT_LABELS[c[1]]}" for c in available_board]
code_by_label = {f"{c[0]}{SUIT_LABELS[c[1]]}": c for c in available_board}
existing_board_codes = st.session_state.get("flop_cards", [])
flop_cols = st.columns(5)
new_board = []
for i in range(5):
    with flop_cols[i]:
        options = flop_options
        current = existing_board_codes[i] if i < len(existing_board_codes) else ""
        current_label = next((k for k, v in code_by_label.items() if v == current), "(선택 안 함)")
        label = st.selectbox(f"보드 카드 {i+1}", options, index=options.index(current_label), key=f"board_{i}")
        if label != "(선택 안 함)":
            new_board.append(code_by_label[label])
# Duplicate board selections are blocked before simulation.
st.session_state["flop_cards"] = new_board
board = [parse_card(c) for c in new_board]
if len(board) not in (0, 3, 4, 5):
    st.warning("보드는 프리플랍(0장), 플랍(3장), 턴(4장), 리버(5장) 단위로 입력하세요.")
if len(set(new_board)) != len(new_board):
    st.error("보드에 같은 카드가 중복 선택되어 있습니다. 중복 카드를 바꿔 주세요.")

flop1, flop2, flop3 = st.columns(3)
with flop1:
    flop_pot = st.number_input("현재 팟 금액(플랍 이후)", min_value=0.0, value=float(pre_pot + pre_call), step=10.0, key="flop_pot")
with flop2:
    flop_call = st.number_input("상대 베팅 / 콜 필요 금액", min_value=0.0, value=0.0, step=10.0, key="flop_call")
with flop3:
    flop_iterations = st.select_slider("플랍 계산 정확도", options=[500, 1000, 2500, 5000, 10000], value=2500, key="flop_iterations")
if st.button("플랍 승률 및 액션 계산", type="primary"):
    if len(board) not in (3, 4, 5):
        st.error("플랍 이후 계산을 위해 보드 카드 3장(플랍), 4장(턴) 또는 5장(리버)을 입력하세요.")
    elif len(set(new_board)) != len(new_board) or set(new_board) & used_hero:
        st.error("내 핸드와 보드에 중복 카드가 있습니다. 카드를 다시 선택하세요.")
    else:
        try:
            with st.spinner("보드 기준 승률을 계산 중..."):
                eq = equity_sim(hero, board, opponents, int(flop_iterations))
            st.session_state["equity_result"] = eq
            st.session_state["last_stage"] = "플랍"
            st.session_state["last_hand"] = hand
        except Exception as exc:
            st.error(str(exc))

if st.session_state.get("last_stage") == "플랍" and st.session_state.get("equity_result") is not None:
    eq = st.session_state["equity_result"]
    action, reason, pot_odds = recommendation(eq, flop_pot, flop_call, st.session_state["seed_stack"], "플랍", players_total)
    m1, m2, m3 = st.columns(3)
    m1.metric("보드 기준 추정 승률(지분)", f"{eq * 100:.1f}%")
    m2.metric("팟 오즈 기준", f"{pot_odds * 100:.1f}%")
    m3.metric("추천 액션", action)
    st.info(reason)

with st.expander("승률과 추천 액션 계산 방식 / 주의사항"):
    st.markdown("""
    - 승률은 선택한 내 카드와 공개 보드를 고정하고, 상대의 비공개 핸드는 무작위라고 가정한 몬테카를로 추정치입니다.
    - 상대의 실제 핸드 범위, 레이즈 크기, 포지션, 플레이 성향, 토너먼트 ICM은 반영하지 않습니다.
    - 추천은 팟 오즈와 추정 지분을 이용한 참고 의견이며, 정답이나 수익 보장을 의미하지 않습니다.
    - 10분마다 블라인드/앤티가 변경되면 사이드바에서 값을 다시 입력할 수 있습니다. 초기화 버튼은 블라인드·앤티만 기본값으로 되돌리고 초기 시드는 유지합니다.
    """)
