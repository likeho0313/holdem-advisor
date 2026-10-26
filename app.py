import random
from itertools import combinations

import streamlit as st
from treys import Card, Deck, Evaluator

st.set_page_config(page_title="홀덤 핸드·액션 어드바이저", page_icon="♠️", layout="wide")

RANKS = "AKQJT98765432"
SUIT_LABELS = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
SUIT_NAMES = {"s": "스페이드", "h": "하트", "d": "다이아", "c": "클럽"}
EVAL = Evaluator()


def card_text(card):
    value = Card.int_to_str(card)
    return value[0] + SUIT_LABELS[value[1]]


def matrix_hand(row_rank, col_rank):
    if row_rank == col_rank:
        return row_rank + col_rank
    if RANKS.index(row_rank) < RANKS.index(col_rank):
        return row_rank + col_rank + "s"
    return col_rank + row_rank + "o"


def combos_for_hand(hand):
    if len(hand) == 2:
        rank = hand[0]
        return [(a, b) for a, b in combinations([rank + s for s in "shdc"], 2)]
    r1, r2, kind = hand[0], hand[1], hand[2]
    if kind == "s":
        return [(r1 + s, r2 + s) for s in "shdc"]
    return [(r1 + s1, r2 + s2) for s1 in "shdc" for s2 in "shdc" if s1 != s2]


def equity_sim(hero, board, opponents, iterations=2500):
    """Estimate equity against random unknown opponent hands by Monte Carlo."""
    if len(hero) != 2 or len(board) not in (0, 3, 4, 5):
        raise ValueError("보드는 0장, 3장, 4장 또는 5장이어야 합니다.")
    known = list(hero) + list(board)
    if len(set(known)) != len(known):
        raise ValueError("내 핸드와 보드 카드가 중복됩니다.")
    if len(hero) + len(board) + opponents * 2 > 52:
        raise ValueError("플레이어 수가 너무 많습니다.")
    deck = [c for c in Deck.GetFullDeck() if c not in known]
    wins_or_split = 0.0
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
            winners = sum(1 for score in scores if score == best)
            wins_or_split += 1 / winners
    return wins_or_split / iterations


def recommendation(equity, pot, to_call, stack, stage):
    pot, to_call, stack = max(0.0, float(pot)), max(0.0, float(to_call)), max(0.0, float(stack))
    pot_odds = to_call / (pot + to_call) if pot + to_call > 0 else 0.0
    if stack <= 0:
        return "폴드", "남은 시드가 없어 추가 베팅할 수 없습니다.", pot_odds
    if to_call <= 0:
        if equity >= 0.65:
            return "베팅/올인 검토", "추정 지분은 높지만 상대 범위와 스택을 함께 고려하세요.", pot_odds
        return "체크 권장", "추가 콜 금액이 없으면 체크할 수 있는 상황입니다.", pot_odds
    if to_call >= stack:
        if equity >= 0.58:
            return "올인 콜 검토", "콜 금액이 남은 시드와 같거나 더 큽니다. 실제 투입은 남은 시드까지만 가능합니다.", pot_odds
        if equity >= pot_odds + 0.08:
            return "콜 검토", "팟 오즈보다 추정 지분이 높지만 큰 팟이 걸린 결정입니다.", pot_odds
        return "폴드 권장", "필요 지분에 비해 추정 지분이 낮습니다.", pot_odds
    if equity >= max(0.48, pot_odds + 0.12):
        return "콜 검토", "팟 오즈 대비 추정 지분이 충분한 편입니다.", pot_odds
    if equity >= pot_odds + 0.03:
        return "콜 또는 폴드", "팟 오즈와 추정 지분 차이가 작아 포지션·상대 범위가 중요합니다.", pot_odds
    return "폴드 권장", "현재 입력 기준으로 콜에 필요한 지분을 충족하지 못합니다.", pot_odds


def on_bb_change():
    bb = float(st.session_state.get("bb", 100))
    st.session_state["sb"] = bb / 2
    # The call amounts default to the new BB. Users can then edit them for the actual bet faced.
    st.session_state["pre_call"] = bb
    st.session_state["flop_call"] = bb
    st.session_state["pre_pot"] = bb + bb / 2 + len(st.session_state.get("opponent_seats", [1, 3, 8]) + [st.session_state.get("player_seat", 6)]) * float(st.session_state.get("ante", 0))
    st.session_state["flop_pot"] = st.session_state["pre_pot"]


def reset_blinds():
    st.session_state["bb"] = 100
    st.session_state["sb"] = 50.0
    st.session_state["ante"] = 0
    st.session_state["pre_call"] = 100.0
    st.session_state["flop_call"] = 100.0
    st.session_state["pre_pot"] = 150.0
    st.session_state["flop_pot"] = 150.0
    st.session_state["equity_result"] = None
    st.session_state["last_stage"] = None


def reset_game():
    defaults = {
        "seed_stack": 10000, "stack_remaining": 10000,
        "bb": 100, "sb": 50.0, "ante": 0,
        "player_seat": 6, "opponent_seats": [1, 3, 8], "start_seat": 1,
        "selected_hand": "AKs", "selected_combo": "As|Ks",
        "flop_cards": [], "pre_pot": 150.0, "pre_call": 100.0,
        "flop_pot": 150.0, "flop_call": 100.0,
        "equity_result": None, "last_stage": None, "last_hand": None,
        "pre_iterations": 2500, "flop_iterations": 2500,
    }
    for key, value in defaults.items():
        st.session_state[key] = value


def init_state():
    defaults = {
        "seed_stack": 10000, "stack_remaining": 10000,
        "bb": 100, "sb": 50.0, "ante": 0,
        "player_seat": 6, "opponent_seats": [1, 3, 8], "start_seat": 1,
        "selected_hand": "AKs", "selected_combo": "As|Ks",
        "flop_cards": [], "pre_pot": 150.0, "pre_call": 100.0,
        "flop_pot": 150.0, "flop_call": 100.0,
        "equity_result": None, "last_stage": None, "last_hand": None,
        "pre_iterations": 2500, "flop_iterations": 2500,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def apply_call(stage):
    call_key = "pre_call" if stage == "pre" else "flop_call"
    pot_key = "pre_pot" if stage == "pre" else "flop_pot"
    requested = max(0.0, float(st.session_state.get(call_key, 0)))
    remaining = max(0.0, float(st.session_state.get("stack_remaining", 0)))
    paid = min(requested, remaining)
    st.session_state["stack_remaining"] = remaining - paid
    st.session_state[pot_key] = max(0.0, float(st.session_state.get(pot_key, 0))) + paid
    st.session_state["last_call_notice"] = f"{stage.upper()} 콜 처리: {paid:,.0f} 투입, 남은 시드 {st.session_state['stack_remaining']:,.0f}, 팟 {st.session_state[pot_key]:,.0f}."
    if stage == "pre":
        # The postflop pot starts from the updated preflop pot.
        st.session_state["flop_pot"] = st.session_state["pre_pot"]
    st.session_state["equity_result"] = None
    st.session_state["last_stage"] = None


init_state()

st.title("♠️ 홀덤 핸드·액션 어드바이저")
st.caption("169개 시작 핸드 조합과 몬테카를로 승률 추정을 이용하는 개인용 참고 도구입니다. 상대의 실제 핸드 범위는 알 수 없으므로 추천은 참고용입니다.")

with st.sidebar:
    st.header("게임 설정")
    st.number_input("초기 시드 / 시작 스택", min_value=1, step=100, key="seed_stack", help="시작 시 보유한 칩입니다. 블라인드·앤티 초기화로 변경되지 않습니다.")
    if st.session_state.get("stack_remaining") is None:
        st.session_state["stack_remaining"] = st.session_state["seed_stack"]
    st.metric("현재 남은 시드", f"{st.session_state['stack_remaining']:,.0f}")
    st.number_input("빅블라인드(BB)", min_value=1, step=10, key="bb", on_change=on_bb_change)
    st.number_input("스몰블라인드(SB = BB ÷ 2)", min_value=0.5, value=float(st.session_state["sb"]), step=5.0, disabled=True)
    st.number_input("앤티(Ante / ENT)", min_value=0, step=5, key="ante")
    c1, c2 = st.columns(2)
    with c1:
        st.button("블라인드·앤티 초기화", use_container_width=True, on_click=reset_blinds)
    with c2:
        st.button("게임 전체 초기화", type="primary", use_container_width=True, on_click=reset_game)
    st.caption("블라인드·앤티 초기화는 BB 100 / SB 50 / 앤티 0으로 되돌립니다. 초기 시드와 현재 남은 시드는 유지됩니다.")
    with st.expander("용어 설명", expanded=True):
        st.markdown("""
        - **초기 시드 / 시작 스택:** 핸드 시작 전에 보유한 칩.
        - **현재 남은 시드:** 콜 버튼으로 팟에 넣은 금액을 뺀 잔액.
        - **SB(스몰 블라인드):** 버튼 왼쪽 첫 강제 베팅. 이 앱에서는 BB의 절반으로 계산.
        - **BB(빅 블라인드):** SB 다음의 강제 베팅이며 기본 콜 금액의 기준값.
        - **앤티(Ante/ENT):** 각 플레이어가 핸드 시작 전에 내는 강제 베팅.
        - **현재 팟:** 이미 팟에 들어간 모든 플레이어의 칩 합계.
        - **콜 필요 금액:** 현재 베팅에 맞추기 위해 내가 추가로 내야 하는 금액. 실제 테이블 금액에 맞춰 수정하세요.
        - **팟 오즈:** 콜 금액과 콜 전 팟을 이용해 계산한 손익분기 승률의 근사치.
        """)

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
    st.multiselect("나 이외의 플레이어 자리", possible_opponents, key="opponent_seats", help="상대의 비공개 핸드는 무작위로 가정해 승률을 계산합니다.")
with seat3:
    st.selectbox("시작 플레이어 자리", list(range(1, 11)), key="start_seat")
opponents = max(1, len(st.session_state["opponent_seats"]))
players_total = len(st.session_state["opponent_seats"]) + 1
st.caption(f"계산 인원: 나 포함 {players_total}명 · 시작 플레이어: {st.session_state['start_seat']}번 · SB {st.session_state['sb']:,.1f} / BB {st.session_state['bb']:,.0f} / 앤티 {st.session_state['ante']:,.0f}")

st.subheader("2. 내 핸드 선택 — 169개 조합표")
st.write("행과 열을 선택해 페어, 수딧, 오프수딧 핸드를 선택하세요.")
rank_cols = st.columns([0.6] + [1] * 13)
rank_cols[0].markdown("**행/열**")
for j, rank in enumerate(RANKS):
    rank_cols[j + 1].markdown(f"**{rank}**")
for i, row_rank in enumerate(RANKS):
    cols = st.columns([0.6] + [1] * 13)
    cols[0].markdown(f"**{row_rank}**")
    for j, col_rank in enumerate(RANKS):
        hand = matrix_hand(row_rank, col_rank)
        if hand == st.session_state["selected_hand"]:
            color_note = "🟥 선택됨"
        elif len(hand) == 2:
            color_note = "🟦 페어"
        elif hand.endswith("s"):
            color_note = "🟩 수딧"
        else:
            color_note = "🟧 오프수딧"
        if cols[j + 1].button(hand, key=f"hand_{i}_{j}", use_container_width=True, help=f"{hand} · {color_note}"):
            st.session_state["selected_hand"] = hand
            st.session_state["equity_result"] = None
            st.rerun()
st.markdown("🟦 페어 · 🟩 수딧(같은 무늬) · 🟧 오프수딧(서로 다른 무늬) · 🟥 현재 선택")
with st.expander("핸드 조합 순위 간단 설명", expanded=True):
    st.markdown("""
    **일반적인 프리플랍 강도는 대략 다음과 같습니다.** 상대 수, 포지션, 스택, 베팅 상황에 따라 순위는 달라집니다.

    1. **최상위 페어:** AA, KK, QQ, JJ — 강한 시작 핸드.
    2. **상위 브로드웨이:** AKs, AKo, AQs — 높은 카드 두 장으로 강한 페어·스트레이트 가능성.
    3. **중상위 페어/수딧:** TT~77, AJs, KQs, KJs, QJs — 대체로 플레이 가치가 높음.
    4. **중간 페어·수딧 연결 핸드:** 66~22, JTs, T9s, 98s — 세트·스트레이트·플러시 가능성이 있으나 보드와 상대에 민감.
    5. **약한 오프수딧 핸드:** 낮은 비연결 카드, 낮은 오프수딧 조합 — 지배당할 가능성이 있어 신중한 플레이가 필요.

    - **페어(예: AA):** 같은 숫자/랭크 두 장.
    - **수딧(s, 예: AKs):** 두 카드의 무늬가 같음.
    - **오프수딧(o, 예: AKo):** 두 카드의 무늬가 다름.
    - 169개 표는 13×13으로 표시하지만 실제 카드 조합은 1,326개입니다.
    """)

hand = st.session_state["selected_hand"]
combos = combos_for_hand(hand)
combo_labels = [f"{a[0]}{SUIT_LABELS[a[1]]}  {b[0]}{SUIT_LABELS[b[1]]}" for a, b in combos]
combo_to_code = {label: f"{a}|{b}" for label, (a, b) in zip(combo_labels, combos)}
current_code = st.session_state.get("selected_combo", "")
current_label = next((label for label, code in combo_to_code.items() if code == current_code), combo_labels[0])
selected_label = st.selectbox("실제 무늬 조합", combo_labels, index=combo_labels.index(current_label), help="보드 카드와 실제 카드가 중복되지 않도록 선택하세요.")
st.session_state["selected_combo"] = combo_to_code[selected_label]
hero_codes = st.session_state["selected_combo"].split("|")
hero = [Card.new(c) for c in hero_codes]
st.write(f"**선택 핸드:** {hand} · 실제 카드: {card_text(hero[0])}, {card_text(hero[1])}")

st.subheader("3. 프리플랍 승률 및 액션 추천")
st.caption("BB를 바꾸면 이 섹션의 기본 콜 금액과 초기 팟이 자동으로 갱신됩니다. 실제 상대 베팅에 맞춰 금액을 조정할 수 있습니다.")
pre1, pre2, pre3 = st.columns(3)
with pre1:
    st.number_input("3. 현재 팟 금액", min_value=0.0, step=10.0, key="pre_pot")
with pre2:
    st.number_input("3. 콜에 필요한 금액", min_value=0.0, step=10.0, key="pre_call")
with pre3:
    st.select_slider("계산 반복 횟수", options=[500, 1000, 2500, 5000, 10000], key="pre_iterations")
pre_buttons = st.columns([1, 1, 2])
with pre_buttons[0]:
    if st.button("3. 콜", use_container_width=True):
        apply_call("pre")
        st.rerun()
with pre_buttons[1]:
    if st.button("3. 폴드", use_container_width=True):
        st.session_state["last_call_notice"] = "프리플랍에서 폴드를 선택했습니다. 시드와 팟은 변경하지 않았습니다."
        st.session_state["equity_result"] = None
        st.session_state["last_stage"] = None
        st.rerun()
with pre_buttons[2]:
    if st.button("프리플랍 승률 계산", type="primary", use_container_width=True):
        try:
            with st.spinner("프리플랍 승률을 계산 중..."):
                eq = equity_sim(hero, [], opponents, int(st.session_state["pre_iterations"]))
            st.session_state["equity_result"] = eq
            st.session_state["last_stage"] = "프리플랍"
            st.session_state["last_hand"] = hand
        except Exception as exc:
            st.error(str(exc))
if st.session_state.get("last_call_notice"):
    st.info(st.session_state["last_call_notice"])
if st.session_state.get("last_stage") == "프리플랍" and st.session_state.get("equity_result") is not None:
    eq = st.session_state["equity_result"]
    action, reason, pot_odds = recommendation(eq, st.session_state["pre_pot"], st.session_state["pre_call"], st.session_state["stack_remaining"], "프리플랍")
    m1, m2, m3 = st.columns(3)
    m1.metric("추정 승률(지분)", f"{eq * 100:.1f}%")
    m2.metric("콜 필요 승률(팟 오즈)", f"{pot_odds * 100:.1f}%")
    m3.metric("추천 액션", action)
    st.info(reason)

st.subheader("4. 플랍 이후 승률 및 액션 추천")
st.caption("BB를 바꾸면 기본 콜 금액이 갱신됩니다. 플랍의 현재 팟은 프리플랍에서 콜 처리한 팟을 이어받으며, 필요하면 직접 수정할 수 있습니다.")
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
        current = existing_board_codes[i] if i < len(existing_board_codes) else ""
        current_label = next((k for k, v in code_by_label.items() if v == current), "(선택 안 함)")
        label = st.selectbox(f"보드 카드 {i+1}", flop_options, index=flop_options.index(current_label), key=f"board_{i}")
        if label != "(선택 안 함)":
            new_board.append(code_by_label[label])
st.session_state["flop_cards"] = new_board
board = [Card.new(c) for c in new_board]
if len(board) not in (0, 3, 4, 5):
    st.warning("보드는 프리플랍 0장, 플랍 3장, 턴 4장 또는 리버 5장으로 입력하세요.")
if len(set(new_board)) != len(new_board):
    st.error("보드 카드가 중복되었습니다. 같은 카드를 두 번 선택하지 마세요.")

flop1, flop2, flop3 = st.columns(3)
with flop1:
    st.number_input("4. 현재 팟 금액", min_value=0.0, step=10.0, key="flop_pot")
with flop2:
    st.number_input("4. 콜에 필요한 금액", min_value=0.0, step=10.0, key="flop_call")
with flop3:
    st.select_slider("계산 반복 횟수", options=[500, 1000, 2500, 5000, 10000], key="flop_iterations")
flop_buttons = st.columns([1, 1, 2])
with flop_buttons[0]:
    if st.button("4. 콜", use_container_width=True):
        apply_call("flop")
        st.rerun()
with flop_buttons[1]:
    if st.button("4. 폴드", use_container_width=True):
        st.session_state["last_call_notice"] = "플랍 이후 폴드를 선택했습니다. 시드와 팟은 변경하지 않았습니다."
        st.session_state["equity_result"] = None
        st.session_state["last_stage"] = None
        st.rerun()
with flop_buttons[2]:
    if st.button("플랍/턴/리버 승률 계산", type="primary", use_container_width=True):
        if len(board) not in (3, 4, 5):
            st.error("보드 카드 3장(플랍), 4장(턴), 5장(리버)을 입력하세요.")
        elif len(set(new_board)) != len(new_board) or set(new_board) & used_hero:
            st.error("내 핸드와 보드에 중복 카드가 있습니다.")
        else:
            try:
                with st.spinner("보드 기준 승률을 계산 중..."):
                    eq = equity_sim(hero, board, opponents, int(st.session_state["flop_iterations"]))
                st.session_state["equity_result"] = eq
                st.session_state["last_stage"] = "플랍"
                st.session_state["last_hand"] = hand
            except Exception as exc:
                st.error(str(exc))
if st.session_state.get("last_stage") == "플랍" and st.session_state.get("equity_result") is not None:
    eq = st.session_state["equity_result"]
    action, reason, pot_odds = recommendation(eq, st.session_state["flop_pot"], st.session_state["flop_call"], st.session_state["stack_remaining"], "플랍")
    m1, m2, m3 = st.columns(3)
    m1.metric("보드 기준 추정 승률(지분)", f"{eq * 100:.1f}%")
    m2.metric("콜 필요 승률(팟 오즈)", f"{pot_odds * 100:.1f}%")
    m3.metric("추천 액션", action)
    st.info(reason)

with st.expander("승률 계산 방식 및 주의사항"):
    st.markdown("""
    - 승률은 내 핸드와 공개 보드를 고정하고, 상대의 비공개 핸드는 무작위라고 가정한 몬테카를로 추정치입니다.
    - 현재 팟 금액과 콜 필요 금액은 실제 테이블 상황에 맞춰 수정하세요. 콜 버튼을 누르면 콜 금액(남은 시드 이내)이 시드에서 차감되고 팟에 더해집니다.
    - 콜 버튼은 앱 안의 계산용 상태만 변경하며 실제 온라인 포커 테이블에 베팅하지 않습니다.
    - 추천은 참고 의견이며, 수익이나 승리를 보장하지 않습니다.
    """)
