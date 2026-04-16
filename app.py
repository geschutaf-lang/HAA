import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.express as px

# --- 설정 ---
st.set_page_config(page_title="HAA Quant Dashboard", layout="wide")

CANARY = ['TIP']
OFFENSIVE = ['SPY', 'IWM', 'VEA', 'VWO', 'IEF', 'TLT', 'VNQ', 'PDBC', 'QQQ']
DEFENSIVE = ['IEF', 'BIL', 'GLD']
TOP_N = 4
MOM_PERIODS = [1, 3, 6, 12]

# --- 함수 정의 ---
@st.cache_data(ttl=3600)
def get_monthly_prices(tickers):
    all_tickers = list(set(tickers + CANARY + DEFENSIVE))
    raw = yf.download(all_tickers, period='15mo', auto_adjust=True, progress=False)['Close']
    monthly = raw.resample('ME').last()
    return monthly

def calc_momentum(prices, ticker):
    latest = prices[ticker].dropna()
    if len(latest) < 13:
        return None, {}
    scores = {}
    total = 0
    for n in MOM_PERIODS:
        ret = latest.iloc[-1] / latest.iloc[-1 - n] - 1
        scores[f'{n}개월'] = ret
        total += ret
    return total, scores

# --- UI 구현 ---
st.title("📈 HAA(Hybrid Asset Allocation) 전략 대시보드")
st.markdown("거시경제 국면을 판단하여 최적의 자산 배분 안을 제시합니다.")

if st.sidebar.button('데이터 새로고침'):
    st.cache_data.clear()

with st.spinner('금융 데이터를 불러오는 중...'):
    prices = get_monthly_prices(OFFENSIVE)
    today = prices.index[-1].date()

# 1단계: 카나리아 지표 확인
tip_total, tip_detail = calc_momentum(prices, 'TIP')

st.header(f"1단계: TIP 카나리아 지표 확인 ({today})")
col1, col2 = st.columns([1, 2])

with col1:
    tip_score_pct = tip_total * 100
    st.metric("TIP 합산 스코어", f"{tip_score_pct:+.2f}%")
    
    if tip_total > 0:
        st.success("✅ 판정: 공격 모드 (Offensive)")
        regime = 'offensive'
    else:
        st.error("❌ 판정: 방어 모드 (Defensive)")
        regime = 'defensive'

with col2:
    # TIP 상세 모멘텀 차트
    tip_df = pd.DataFrame(list(tip_detail.items()), columns=['기간', '수익률'])
    tip_df['수익률'] = tip_df['수익률'] * 100
    fig_tip = px.bar(tip_df, x='기간', y='수익률', text_auto='.2f', 
                     title="TIP 기간별 수익률 (%)",
                     color='수익률', color_continuous_scale='RdYlGn')
    st.plotly_chart(fig_tip, use_container_width=True)

st.divider()

# 2단계: 자산 모멘텀 비교
st.header(f"2단계: {'공격' if regime == 'offensive' else '방어'} 자산 모멘텀 분석")

target_universe = OFFENSIVE if regime == 'offensive' else DEFENSIVE
results = []

for ticker in target_universe:
    total, detail = calc_momentum(prices, ticker)
    if total is not None:
        res = {'티커': ticker, '합산 스코어(%)': total * 100}
        for k, v in detail.items():
            res[k] = v * 100
        results.append(res)

res_df = pd.DataFrame(results).sort_values(by='합산 스코어(%)', ascending=False)
res_df = res_df.reset_index(drop=True)

# 순위 부여 및 시각화
st.dataframe(res_df.style.format(precision=2).background_gradient(subset=['합산 스코어(%)'], cmap='RdYlGn'), 
             use_container_width=True)

st.divider()

# 3단계: 액션 플랜
st.header("📋 이번 달 포트폴리오 액션 플랜")
action_col1, action_col2 = st.columns(2)

with action_col1:
    if regime == 'offensive':
        top4_list = res_df.head(TOP_N)['티커'].tolist()
        st.subheader("매수 대상 (각 25%)")
        for i, t in enumerate(top4_list):
            st.info(f"{i+1}. {t} (25.0%)")
    else:
        best_def = res_df.iloc[0]['티커']
        st.subheader("매수 대상 (100%)")
        st.warning(f"1. {best_def} (100.0%)")

with action_col2:
    st.subheader("운용 지침")
    st.markdown(f"""
    - **리밸런싱 기준일**: {today} (종가 기준)
    - **매도**: 현재 보유 종목 중 위 리스트에 없는 종목은 전량 매도
    - **매수**: 위 리스트의 종목을 정해진 비중대로 매수
    - **데이터**: 야후 파이낸스 수정 주가(Adjusted Close) 기준
    """)

st.sidebar.markdown("---")
st.sidebar.info("HAA 전략은 보우터 켈러가 고안한 동적 자산 배분 모델로, 물가연동채(TIP)를 통해 시장의 하락 신호를 선제적으로 포착합니다.")