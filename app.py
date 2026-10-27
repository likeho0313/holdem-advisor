import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import re
import random
from datetime import datetime, timedelta

# ==========================================
# 0. 페이지 기본 설정 및 테마 CSS
# ==========================================
st.set_page_config(
    page_title="HM3 Lite - Poker Data Analytics",
    page_icon="♠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# HM3 스타일의 어두운 테마 및 커스텀 카드 UI 스타일
st.markdown("""
    <style>
    .main {
        background-color: #0e1117;
    }
    .metric-card {
        background-color: #1e222b;
        border-radius: 10px;
        padding: 15px;
        border: 1px solid #2e3440;
        text-align: center;
        margin-bottom: 10px;
    }
    .metric-title {
        font-size: 0.85rem;
        color: #8892b0;
        margin-bottom: 5px;
    }
    .metric-value {
        font-size: 1.6rem;
        font-weight: bold;
        color: #e6f1ff;
    }
    .hud-badge {
        padding: 4px 10px;
        border-radius: 5px;
        font-weight: bold;
        font-size: 0.9rem;
        display: inline-block;
    }
    .tag-tag { background-color: #00bcd4; color: black; }
    .tag-lag { background-color: #ff9800; color: black; }
    .tag-fish { background-color: #4caf50; color: white; }
    .tag-nit { background-color: #9c27b0; color: white; }
    .tag-maniac { background-color: #f44336; color: white; }
    </style>
""", unsafe_allow_html=True)


# ==========================================
# 1. 포커 핸드 히스토리 파서 (PokerStars Style)
# ==========================================
class PokerHandParser:
    """PokerStars 형식의 핸드 히스토리 텍스트 파싱 클래스"""
    
    @staticmethod
    def parse_text(text_content):
        hands_raw = text_content.strip().split("\n\n\n")
        if len(hands_raw) <= 1:
            hands_raw = text_content.strip().split("\n\n")
            
        parsed_hands = []
        parsed_actions = []
        
        for raw_hand in hands_raw:
            if not raw_hand.strip():
                continue
                
            hand_id_match = re.search(r"Hand #(\d+):", raw_hand)
            if not hand_id_match:
                continue
            hand_id = hand_id_match.group(1)
            
            # 판돈(Stakes)
            stakes_match = re.search(r"\(\$(\d+\.\d+)/\$(\d+\.\d+)", raw_hand)
            sb_val = float(stakes_match.group(1)) if stakes_match else 0.50
            bb_val = float(stakes_match.group(2)) if stakes_match else 1.00
            
            # 버튼 / 포지션 파싱
            seats = re.findall(r"Seat (\d+): ([^\(]+) \(\$(\d+\.\d+) in chips\)", raw_hand)
            players = [s[1].strip() for s in seats]
            
            if not players:
                continue
                
            # 섹션 분할
            sections = raw_hand.split("*** ")
            preflop_str = ""
            flop_str = ""
            turn_str = ""
            river_str = ""
            summary_str = ""
            
            for sec in sections:
                if sec.startswith("HOLE CARDS ***"):
                    preflop_str = sec
                elif sec.startswith("FLOP ***"):
                    flop_str = sec
                elif sec.startswith("TURN ***"):
                    turn_str = sec
                elif sec.startswith("RIVER ***"):
                    river_str = sec
                elif sec.startswith("SUMMARY ***"):
                    summary_str = sec
            
            # 보드 카드 파싱
            board_match = re.search(r"Board \[([^\]]+)\]", raw_hand)
            board_cards = board_match.group(1) if board_match else ""
            
            # 총 팟 크기 파싱
            pot_match = re.search(r"Total pot \$(\d+\.?\d*)", raw_hand)
            total_pot = float(pot_match.group(1)) if pot_match else 0.0
            
            # 각 플레이어별 세부 액션 및 승패 집계
            for p in players:
                # 액션 추출
                p_lines = [line for line in raw_hand.split("\n") if line.startswith(f"{p}:")]
                
                vpip = False
                pfr = False
                three_bet = False
                bets_cnt = 0
                raises_cnt = 0
                calls_cnt = 0
                folds_cnt = 0
                saw_showdown = False
                
                # Preflop 액션 검사
                pf_lines = [l for l in preflop_str.split("\n") if l.startswith(f"{p}:")]
                for l in pf_lines:
                    if "raises" in l:
                        vpip = True
                        pfr = True
                        raises_cnt += 1
                        if "raises" in preflop_str.split(l)[0]: # 이전 리레이즈 존재 시 3-bet
                            three_bet = True
                    elif "calls" in l:
                        vpip = True
                        calls_cnt += 1
                    elif "bets" in l:
                        vpip = True
                        bets_cnt += 1
                    elif "folds" in l:
                        folds_cnt += 1
                
                # Postflop 액션 검사
                postflop_str = flop_str + turn_str + river_str
                p_post_lines = [l for l in postflop_str.split("\n") if l.startswith(f"{p}:")]
                for l in p_post_lines:
                    if "raises" in l:
                        raises_cnt += 1
                    elif "bets" in l:
                        bets_cnt += 1
                    elif "calls" in l:
                        calls_cnt += 1
                    elif "folds" in l:
                        folds_cnt += 1
                
                # Showdown 판단
                if "shows" in raw_hand and p in raw_hand:
                    saw_showdown = True
                
                # 순수익(Net Won) 및 승자 계산
                collected = 0.0
                collect_match = re.findall(rf"{re.escape(p)} collected \$(\d+\.?\d*)", raw_hand)
                if collect_match:
                    collected = sum([float(x) for x in collect_match])
                
                # 베팅금 추정 (간이 계산)
                invested = (calls_cnt + bets_cnt + raises_cnt) * bb_val
                if pfr:
                    invested += bb_val * 2.5
                net_won = collected - invested

                parsed_actions.append({
                    "hand_id": hand_id,
                    "player": p,
                    "vpip": 1 if vpip else 0,
                    "pfr": 1 if pfr else 0,
                    "three_bet": 1 if three_bet else 0,
                    "bets": bets_cnt,
                    "raises": raises_cnt,
                    "calls": calls_cnt,
                    "folds": folds_cnt,
                    "saw_showdown": 1 if saw_showdown else 0,
                    "won_at_showdown": 1 if (saw_showdown and collected > 0) else 0,
                    "collected": collected,
                    "net_won": net_won,
                    "board": board_cards,
                    "total_pot": total_pot,
                    "raw_hand": raw_hand
                })
                
        return pd.DataFrame(parsed_actions)


# ==========================================
# 2. 샘플 더미 데이터 생성기 (테스트용)
# ==========================================
@st.cache_data
def generate_sample_hand_data(num_hands=150):
    """업로드 파일이 없을 때 앱 테스트를 위한 가상 핸드 데이타 생성기"""
    players = ["Hero", "GTO_Master", "Fish_Pro", "CallingStation", "AggroKid", "RockSolid"]
    data = []
    
    start_time = datetime.now() - timedelta(days=5)
    
    for i in range(1, num_hands + 1):
        hand_id = f"2401{i:04d}"
        timestamp = start_time + timedelta(minutes=i * 3)
        board_cards = random.choice(["As Kd 7h Jc 2s", "Qh Th 4c 9d", "7s 8s 9c", "Ac Kh Qs Jd 10h", "2c 5d 9h"])
        pot = round(random.uniform(4.0, 120.0), 2)
        
        # 6명 플레이어 배정
        for p in players:
            # 플레이어 성향별 확률 부여
            if p == "Hero":
                vpip = 1 if random.random() < 0.24 else 0
                pfr = 1 if (vpip and random.random() < 0.75) else 0
            elif p == "Fish_Pro":
                vpip = 1 if random.random() < 0.55 else 0
                pfr = 1 if (vpip and random.random() < 0.20) else 0
            elif p == "AggroKid":
                vpip = 1 if random.random() < 0.38 else 0
                pfr = 1 if (vpip and random.random() < 0.80) else 0
            else:
                vpip = 1 if random.random() < 0.20 else 0
                pfr = 1 if (vpip and random.random() < 0.70) else 0

            three_bet = 1 if (pfr and random.random() < 0.25) else 0
            bets = random.randint(0, 2) if vpip else 0
            raises = (1 if pfr else 0) + (1 if three_bet else 0)
            calls = random.randint(0, 2) if vpip else 0
            folds = 1 if (not vpip or random.random() < 0.6) else 0
            saw_sd = 1 if (vpip and folds == 0 and random.random() < 0.4) else 0
            won_sd = 1 if (saw_sd and random.random() < 0.55) else 0
            
            # 수익 계산
            if won_sd:
                net_won = round(pot * random.uniform(0.7, 1.0), 2)
            elif vpip:
                net_won = -round(random.uniform(2.0, 25.0), 2)
            else:
                net_won = -0.5 if random.random() < 0.3 else 0.0
                
            raw_text = f"""PokerStars Hand #{hand_id}: Hold'em No Limit ($0.50/$1.00 USD) - {timestamp.strftime('%Y/%m/%d %H:%M:%S')} ET
Table 'Alpha' 6-max Seat #1 is the button
Seat 1: Hero ($100.00 in chips)
Seat 2: GTO_Master ($120.00 in chips)
Seat 3: Fish_Pro ($45.00 in chips)
Seat 4: CallingStation ($85.00 in chips)
Seat 5: AggroKid ($210.00 in chips)
Seat 6: RockSolid ($100.00 in chips)
*** HOLE CARDS ***
Dealt to Hero [Ah Kd]
{p}: {'raises $3.00' if pfr else ('calls $1.00' if vpip else 'folds')}
*** SUMMARY ***
Total pot ${pot} | Board [{board_cards}]
Player {p} {'won' if won_sd else 'folded'}
"""
            data.append({
                "hand_id": hand_id,
                "timestamp": timestamp,
                "player": p,
                "vpip": vpip,
                "pfr": pfr,
                "three_bet": three_bet,
                "bets": bets,
                "raises": raises,
                "calls": calls,
                "folds": folds,
                "saw_showdown": saw_sd,
                "won_at_showdown": won_sd,
                "collected": pot if won_sd else 0.0,
                "net_won": net_won,
                "board": board_cards,
                "total_pot": pot,
                "raw_hand": raw_text
            })
            
    return pd.DataFrame(data)


# ==========================================
# 3. 데이터 로딩 및 사이드바
# ==========================================
st.sidebar.title("♠️ HM3 Lite Manager")
st.sidebar.markdown("---")

uploaded_file = st.sidebar.file_uploader("핸드 히스토리 파일 (.txt)", type=["txt"])

if uploaded_file is not None:
    content = uploaded_file.read().decode("utf-8")
    df = PokerHandParser.parse_text(content)
    st.sidebar.success(f"파일 파싱 완료: {df['hand_id'].nunique()}개 핸드")
else:
    st.sidebar.info("💡 샘플 핸드 데이터를 기본 사용 중입니다.")
    df = generate_sample_hand_data()

# 플레이어 선택 필터
all_players = sorted(df['player'].unique().tolist())
selected_player = st.sidebar.selectbox("메인 히어로(Hero) 선택", all_players, index=0)

# 선택된 플레이어 데이터 필터링
player_df = df[df['player'] == selected_player].copy().reset_index(drop=True)


# ==========================================
# 4. 플레이어 포커 성향(Archetype) 판별 함수
# ==========================================
def get_player_style(vpip, pfr, af):
    if vpip >= 35 and pfr >= 25:
        return "Maniac (매니악)", "tag-maniac"
    elif vpip >= 28 and pfr >= 20 and af >= 2.0:
        return "LAG (Loose-Aggressive)", "tag-lag"
    elif vpip < 25 and pfr >= 15 and af >= 1.8:
        return "TAG (Tight-Aggressive)", "tag-tag"
    elif vpip >= 30 and pfr < 15:
        return "Calling Station (콜링 스테이션)", "tag-fish"
    elif vpip < 18 and pfr < 12:
        return "Rock / Nit (바위)", "tag-nit"
    else:
        return "Passive / Balanced", "tag-tag"


# ==========================================
# 5. 메인 UI 탭 구성
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 포커 통계 대시보드", 
    "👤 가상 HUD & 프로필", 
    "🎬 핸드 리플레이어", 
    "📋 파싱 데이터 테이블"
])


# ------------------------------------------
# TAB 1: 포커 통계 대시보드
# ------------------------------------------
with tab1:
    st.subheader(f"📈 {selected_player} 님의 주요 성과 및 통계")
    
    total_hands = len(player_df)
    vpip_pct = (player_df['vpip'].sum() / total_hands * 100) if total_hands > 0 else 0
    pfr_pct = (player_df['pfr'].sum() / total_hands * 100) if total_hands > 0 else 0
    three_bet_pct = (player_df['three_bet'].sum() / total_hands * 100) if total_hands > 0 else 0
    
    total_calls = player_df['calls'].sum()
    total_agg = player_df['bets'].sum() + player_df['raises'].sum()
    af_val = round(total_agg / total_calls, 2) if total_calls > 0 else total_agg
    
    showdowns = player_df['saw_showdown'].sum()
    wsd_pct = (player_df['won_at_showdown'].sum() / showdowns * 100) if showdowns > 0 else 0
    net_won_total = player_df['net_won'].sum()

    # KPI 카드가 들어가는 상단 컬럼
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("총 핸드 수", f"{total_hands:,}개")
    col2.metric("Net Won", f"${net_won_total:,.2f}", delta=f"{net_won_total:,.2f}")
    col3.metric("VPIP", f"{vpip_pct:.1f}%")
    col4.metric("PFR", f"{pfr_pct:.1f}%")
    col5.metric("3-Bet %", f"{three_bet_pct:.1f}%")
    col6.metric("AF (공격성)", f"{af_val}")

    st.markdown("---")
    
    # 누적 수익 라인 차트 (Cumulative Net Won)
    st.subheader("💵 누적 수익 그래프 (Net Won Graph)")
    player_df['cum_net_won'] = player_df['net_won'].cumsum()
    player_df['hand_num'] = np.arange(1, len(player_df) + 1)
    
    fig_cum = px.line(
        player_df, 
        x='hand_num', 
        y='cum_net_won',
        labels={'hand_num': '핸드 수', 'cum_net_won': '누적 수익 ($)'},
        title=f"{selected_player}의 핸드 진행별 누적 그래프"
    )
    fig_cum.update_traces(line_color="#00e676" if net_won_total >= 0 else "#ff5252", line_width=2.5)
    fig_cum.add_hline(y=0, line_dash="dash", line_color="gray")
    fig_cum.update_layout(template="plotly_dark", height=400)
    st.plotly_chart(fig_cum, use_container_width=True)


# ------------------------------------------
# TAB 2: 가상 HUD & 플레이어 프로필
# ------------------------------------------
with tab2:
    st.subheader("👤 플레이어 성향 검색 및 Virtual HUD")
    
    search_p = st.selectbox("조회할 플레이어 선택", all_players, index=all_players.index(selected_player))
    p_df = df[df['player'] == search_p]
    p_hands = len(p_df)
    
    p_vpip = (p_df['vpip'].sum() / p_hands * 100) if p_hands > 0 else 0
    p_pfr = (p_df['pfr'].sum() / p_hands * 100) if p_hands > 0 else 0
    p_3bet = (p_df['three_bet'].sum() / p_hands * 100) if p_hands > 0 else 0
    p_calls = p_df['calls'].sum()
    p_agg = p_df['bets'].sum() + p_df['raises'].sum()
    p_af = round(p_agg / p_calls, 2) if p_calls > 0 else p_agg
    p_sd = p_df['saw_showdown'].sum()
    p_wsd = (p_df['won_at_showdown'].sum() / p_sd * 100) if p_sd > 0 else 0
    
    style_label, style_class = get_player_style(p_vpip, p_pfr, p_af)
    
    # HUD 패널 카드 UI
    st.markdown(f"""
        <div style="background-color: #1a1e24; padding: 20px; border-radius: 12px; border: 2px solid #2d3748;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h2>♠️ {search_p}</h2>
                <span class="hud-badge {style_class}">{style_label}</span>
            </div>
            <hr style="border-color: #2d3748; margin: 10px 0;">
            <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; text-align: center;">
                <div><div class="metric-title">VPIP</div><div class="metric-value">{p_vpip:.1f}%</div></div>
                <div><div class="metric-title">PFR</div><div class="metric-value">{p_pfr:.1f}%</div></div>
                <div><div class="metric-title">3-BET</div><div class="metric-value">{p_3bet:.1f}%</div></div>
                <div><div class="metric-title">AF</div><div class="metric-value">{p_af}</div></div>
                <div><div class="metric-title">WSD%</div><div class="metric-value">{p_wsd:.1f}%</div></div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 레이더 차트를 통한 플레이어 성향 레이어 분석
    st.write("##### 🎯 능력치 다이어그램")
    radar_categories = ['VPIP', 'PFR', '3-Bet', 'Aggression Factor', 'WSD%']
    radar_values = [min(p_vpip, 100), min(p_pfr, 100), min(p_3bet * 3, 100), min(p_af * 20, 100), min(p_wsd, 100)]
    
    fig_radar = go.Figure(data=go.Scatterpolar(
        r=radar_values,
        theta=radar_categories,
        fill='toself',
        fillcolor='rgba(0, 188, 212, 0.3)',
        line=dict(color='#00bcd4', width=2)
    ))
    fig_radar.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=False,
        template="plotly_dark",
        height=350
    )
    st.plotly_chart(fig_radar, use_container_width=True)


# ------------------------------------------
# TAB 3: 핸드 리플레이어 (Hand Replayer)
# ------------------------------------------
with tab3:
    st.subheader("🎬 핸드 리플레이어 (Hand Replayer)")
    
    hand_ids = player_df['hand_id'].unique().tolist()
    selected_hand_id = st.selectbox("복기할 핸드 ID 선택", hand_ids)
    
    hand_rows = df[df['hand_id'] == selected_hand_id]
    first_row = hand_rows.iloc[0]
    
    col_rep1, col_rep2 = st.columns([1, 1])
    
    with col_rep1:
        st.markdown("##### 🃏 핸드 요약 정보")
        st.info(f"**Hand ID:** #{selected_hand_id}")
        st.write(f"**보드 카드:** `{first_row['board'] if first_row['board'] else '없음 (Pre-flop 종료)'}`")
        st.write(f"**최종 팟 크기:** `${first_row['total_pot']:.2f}`")
        
        # 승자 및 수익 표시
        winners = hand_rows[hand_rows['collected'] > 0]
        if not winners.empty:
            for _, w in winners.iterrows():
                st.success(f"🏆 승자: **{w['player']}** (+$ {w['collected']:.2f})")
                
    with col_rep2:
        st.markdown("##### 📜 원본 텍스트로그 (Raw Hand History)")
        st.code(first_row['raw_hand'], language="text")


# ------------------------------------------
# TAB 4: 파싱 데이터 테이블
# ------------------------------------------
with tab4:
    st.subheader("📋 전체 파싱 데이터 검토 및 내보내기")
    
    st.dataframe(df, use_container_width=True)
    
    # CSV 다운로드 버튼
    csv_data = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 CSV 파일로 다운로드",
        data=csv_data,
        file_name=f"parsed_poker_hands_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )
