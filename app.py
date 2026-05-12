import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
 
# ──────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────
st.set_page_config(page_title="HAA Quant Dashboard", layout="wide")
 
CANARY    = 'TIP'
OFFENSIVE = ['SPY', 'IWM', 'VEA', 'VWO, 'VNQ', 'DBC', 'IEF', 'TLT', 'GLD]
DEFENSIVE = ['SHY', 'IEF', 'BIL', 'GLD]
TOP_N     = 4
MOM_PERIODS = [1, 3, 6, 12]
 
TICKER_NAMES = {
    'SPY': 'S&P500',    'IWM': '미국소형주',  'VNQ': '리츠',
    'GLD': '금',         'DBC': '원자재',      'TLT': '장기국채',
    'IEF': '중기국채',   'BIL': '초단기채',     'TIP': '물가연동채(카나리아)',
}
 
 
# ──────────────────────────────────────────────
# 데이터 & 모멘텀
# ──────────────────────────────────────────────
@st.cache_data(ttl=86400, show_spinner=False)
def get_monthly_prices():
    all_tickers = list(set(OFFENSIVE + DEFENSIVE + [CANARY]))
    raw = yf.download(all_tickers, period='3y', auto_adjust=True, progress=False)['Close']
    monthly = raw.resample('ME').last()
    monthly = monthly.dropna(axis=1, thresh=len(monthly) // 2)
    return monthly
 
 
def calc_momentum(prices: pd.DataFrame, ticker: str):
    """Keller식 평균 모멘텀 = (r1 + r3 + r6 + r12) / 4"""
    if ticker not in prices.columns:
        return None, {}
    p = prices[ticker].dropna()
    if len(p) < 13:
        return None, {}
 
    detail = {}
    total  = 0
    for n in MOM_PERIODS:
        ret = p.iloc[-1] / p.iloc[-1 - n] - 1
        detail[f'{n}개월'] = ret
        total += ret
 
    avg_mom = total / len(MOM_PERIODS)  # 평균 모멘텀
    return avg_mom, detail
 
 
# ──────────────────────────────────────────────
# UI
# ──────────────────────────────────────────────
st.title("📈 HAA (Hybrid Asset Allocation) 전략 대시보드")
st.markdown("물가연동채(TIP)를 카나리아로 활용해 시장 국면을 판단하고, 최적 자산 배분안을 제시합니다.")
 
# 사이드바
with st.sidebar:
    st.header("⚙️ 설정")
    if st.button('🔄 데이터 새로고침', use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.markdown("---")
    st.markdown("**전략 개요**")
    st.markdown("""
    - **카나리아**: TIP (물가연동채)
    - **공격 자산**: 11개 ETF 중 모멘텀 Top 4
    - **방어 자산**: SHY/IEF/BIL 중 모멘텀 1위
    - **리밸런싱**: 월 1회
    - **모멘텀**: (1+3+6+12개월 수익률) / 4
    """)
    st.markdown("---")
    st.caption("Keller & Keuning (2022) HAA 논문 기준")
 
# 데이터 로딩
with st.spinner('금융 데이터를 불러오는 중...'):
    prices = get_monthly_prices()
    today  = prices.index[-1].strftime('%Y년 %m월 %d일')
 
st.caption(f"기준일: {today} (월말 종가 기준) | 데이터: Yahoo Finance")
st.divider()
 
 
# ──────────────────────────────────────────────
# 1단계: 카나리아 판단
# ──────────────────────────────────────────────
st.header("1️⃣ 카나리아 지표 (TIP)")
 
tip_mom, tip_detail = calc_momentum(prices, CANARY)
 
if tip_mom is None:
    st.error("TIP 데이터를 불러올 수 없습니다.")
    st.stop()
 
col1, col2 = st.columns([1, 2])
 
with col1:
    st.metric("TIP 평균 모멘텀", f"{tip_mom*100:+.2f}%")
    if tip_mom > 0:
        st.success("✅ 공격 모드 (Offensive)")
        regime = 'offensive'
    else:
        st.error("❌ 방어 모드 (Defensive)")
        regime = 'defensive'
 
    st.markdown("**기간별 수익률**")
    for k, v in tip_detail.items():
        color = "🟢" if v > 0 else "🔴"
        st.markdown(f"{color} {k}: `{v*100:+.2f}%`")
 
with col2:
    tip_df = pd.DataFrame([
        {'기간': k, '수익률(%)': v * 100}
        for k, v in tip_detail.items()
    ])
    fig_tip = px.bar(
        tip_df, x='기간', y='수익률(%)',
        text_auto='.2f',
        title="TIP 기간별 수익률",
        color='수익률(%)',
        color_continuous_scale='RdYlGn',
        color_continuous_midpoint=0,
    )
    fig_tip.add_hline(y=0, line_dash='dash', line_color='black', line_width=1)
    fig_tip.update_layout(showlegend=False, coloraxis_showscale=False)
    st.plotly_chart(fig_tip, use_container_width=True)
 
st.divider()
 
 
# ──────────────────────────────────────────────
# 2단계: 자산 모멘텀 분석
# ──────────────────────────────────────────────
universe = OFFENSIVE if regime == 'offensive' else DEFENSIVE
mode_label = '공격' if regime == 'offensive' else '방어'
st.header(f"2️⃣ {mode_label} 자산 모멘텀 분석")
 
results = []
for tk in universe:
    mom, detail = calc_momentum(prices, tk)
    if mom is not None:
        row = {
            '티커': tk,
            '종목명': TICKER_NAMES.get(tk, tk),
            '평균 모멘텀(%)': mom * 100,
        }
        for k, v in detail.items():
            row[k] = v * 100
        results.append(row)
 
if not results:
    st.error("모멘텀 계산 가능한 종목이 없습니다.")
    st.stop()
 
res_df = pd.DataFrame(results).sort_values('평균 모멘텀(%)', ascending=False).reset_index(drop=True)
res_df.index += 1  # 1부터 시작
 
# 상위 선택 종목 강조
if regime == 'offensive':
    selected = res_df.head(TOP_N)['티커'].tolist()
else:
    selected = [res_df.iloc[0]['티커']]
 
def highlight_selected(row):
    if row['티커'] in selected:
        return ['background-color: #d4edda'] * len(row)
    return [''] * len(row)
 
st.dataframe(
    res_df.style
          .apply(highlight_selected, axis=1)
          .format({col: '{:+.2f}%' for col in res_df.columns if '%' in col}),
    use_container_width=True,
    height=420,
)
 
# 모멘텀 바 차트
fig_mom = px.bar(
    res_df.sort_values('평균 모멘텀(%)'),
    x='평균 모멘텀(%)', y='티커',
    orientation='h',
    text_auto='.2f',
    title=f"{mode_label} 자산 모멘텀 순위",
    color='평균 모멘텀(%)',
    color_continuous_scale='RdYlGn',
    color_continuous_midpoint=0,
    hover_data=['종목명'],
)
fig_mom.add_vline(x=0, line_dash='dash', line_color='black', line_width=1)
fig_mom.update_layout(coloraxis_showscale=False, yaxis_title='')
 
# 선택된 종목 표시
for tk in selected:
    row = res_df[res_df['티커'] == tk]
    if not row.empty:
        fig_mom.add_annotation(
            x=row['평균 모멘텀(%)'].values[0],
            y=tk,
            text="  ✅ 선택",
            showarrow=False,
            font=dict(color='green', size=12),
            xanchor='left',
        )
 
st.plotly_chart(fig_mom, use_container_width=True)
st.divider()
 
 
# ──────────────────────────────────────────────
# 3단계: 이번 달 액션 플랜
# ──────────────────────────────────────────────
st.header("3️⃣ 이번 달 포트폴리오 액션 플랜")
 
col_left, col_right = st.columns(2)
 
with col_left:
    st.subheader("📌 매수 대상")
    if regime == 'offensive':
        weight = 100 / TOP_N
        for i, tk in enumerate(selected):
            name = TICKER_NAMES.get(tk, tk)
            score = res_df[res_df['티커'] == tk]['평균 모멘텀(%)'].values[0]
            st.info(f"**{i+1}. {tk}** ({name})  \n비중: `{weight:.1f}%` | 모멘텀: `{score:+.2f}%`")
    else:
        tk   = selected[0]
        name = TICKER_NAMES.get(tk, tk)
        score = res_df[res_df['티커'] == tk]['평균 모멘텀(%)'].values[0]
        st.warning(f"**1. {tk}** ({name})  \n비중: `100.0%` | 모멘텀: `{score:+.2f}%`")
 
with col_right:
    st.subheader("📋 운용 지침")
    st.markdown(f"""
    - **국면**: {'🟢 공격 (TIP 양수)' if regime == 'offensive' else '🔴 방어 (TIP 음수)'}
    - **리밸런싱 기준**: {today} 종가
    - **매도**: 현재 보유 중 위 리스트 외 종목 → 전량 매도
    - **매수**: 위 종목을 정해진 비중으로 매수
    - **다음 점검일**: 다음 달 말일
    """)
 
    # 비중 파이차트
    if regime == 'offensive':
        pie_labels = [f"{tk}\n({TICKER_NAMES.get(tk,tk)})" for tk in selected]
        pie_values = [100 / TOP_N] * len(selected)
    else:
        pie_labels = [f"{selected[0]}\n({TICKER_NAMES.get(selected[0],selected[0])})"]
        pie_values = [100]
 
    fig_pie = go.Figure(go.Pie(
        labels=pie_labels,
        values=pie_values,
        hole=0.4,
        textinfo='label+percent',
    ))
    fig_pie.update_layout(
        title='포트폴리오 비중',
        showlegend=False,
        margin=dict(t=40, b=0, l=0, r=0),
        height=300,
    )
    st.plotly_chart(fig_pie, use_container_width=True)
 
st.divider()
st.caption("※ 본 대시보드는 Keller & Keuning (2022) HAA 논문을 기반으로 한 참고용 자료입니다. 투자 결과에 대한 책임은 본인에게 있습니다.")
 
