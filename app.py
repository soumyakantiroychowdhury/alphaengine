import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# --- HYBRID ALPHA ENGINE V2 (Horizon Aware) ---
class AlphaEngineV2:
    def __init__(self, ticker, target_pct, stop_pct, market, horizon_months):
        self.ticker = ticker.strip().upper()
        self.target_pct = target_pct / 100
        self.stop_pct = stop_pct / 100
        self.horizon = horizon_months
        self.benchmark_ticker = "^GSPC" if market == "US" else "^NSEI"
        
    def get_data(self):
        # Dynamically fetch more history for longer horizons
        period = "2y" if self.horizon < 12 else "5y"
        df = yf.download(self.ticker, period=period, interval="1d", progress=False, multi_level_index=False)
        bench = yf.download(self.benchmark_ticker, period=period, interval="1d", progress=False, multi_level_index=False)
        
        if df.empty or bench.empty:
            return None, None, None
            
        info = yf.Ticker(self.ticker).info
        return df, bench, info

    def calculate_score(self, df, bench, info):
        close_price = df['Close']
        bench_close = bench['Close']

        # --- DYNAMIC INDICATOR LOGIC ---
        # Short horizon (1-4 mo): Focus on 20/50 SMA
        # Long horizon (12+ mo): Focus on 50/200 SMA
        if self.horizon <= 4:
            fast_ma_p, slow_ma_p = 20, 50
            rs_period = 21 # 1 month
        elif self.horizon <= 12:
            fast_ma_p, slow_ma_p = 50, 100
            rs_period = 63 # 3 months
        else:
            fast_ma_p, slow_ma_p = 50, 200
            rs_period = 126 # 6 months

        df['Fast_MA'] = close_price.rolling(fast_ma_p).mean()
        df['Slow_MA'] = close_price.rolling(slow_ma_p).mean()
        df['RVOL'] = df['Volume'] / df['Volume'].rolling(20).mean()
        
        # Relative Strength vs Benchmark
        stock_ret = ((close_price.iloc[-1] / close_price.iloc[-rs_period]) - 1)
        bench_ret = ((bench_close.iloc[-1] / bench_close.iloc[-rs_period]) - 1)
        rs_value = stock_ret - bench_ret
        
        score = 0
        latest = df.iloc[-1]
        
        # 1. Trend Factor (50%)
        if latest['Close'] > latest['Fast_MA']: score += 25
        if latest['Fast_MA'] > latest['Slow_MA']: score += 25
        
        # 2. Relative Strength (25%)
        if rs_value > 0: score += 25
        
        # 3. Volume & Fundamentals (25%)
        if latest['RVOL'] > 1.1: score += 15
        growth = info.get('earningsQuarterlyGrowth')
        if growth and growth > 0.1: score += 10
        
        return round(score, 1), rs_value, latest['Close'], df, fast_ma_p, slow_ma_p

# --- STREAMLIT UI ---
st.set_page_config(page_title="Alpha Engine Pro", layout="centered")

st.title("🚀 Alpha Engine v2")
st.markdown("### Strategic Medium-to-Long Term Guidance")

# Sidebar Configuration
st.sidebar.header("🎯 Strategy Setup")
market_type = st.sidebar.selectbox("Market", ["India", "US"])
ticker_input = st.sidebar.text_input("Ticker", "RELIANCE.NS" if market_type == "India" else "AAPL")

# THE NEW INPUT: Investment Horizon
horizon = st.sidebar.slider("Investment Horizon (Months)", min_value=1, max_value=24, value=3, help="Adjusts indicators: shorter = faster MAs, longer = slower trend-following MAs.")

target_profit = st.sidebar.number_input("Target Profit (%)", 5, 50, 12)
stop_loss = st.sidebar.number_input("Stop Loss (%)", 3, 20, 5)

if st.button("Generate Guidance"):
    with st.spinner('Analyzing time-series and fundamental data...'):
        engine = AlphaEngineV2(ticker_input, target_profit, stop_loss, market_type, horizon)
        df, bench, info = engine.get_data()
        
        if df is not None:
            score, rs, current_price, df_final, f_ma, s_ma = engine.calculate_score(df, bench, info)
            
            # Action Recommendation
            if score >= 75: status, color = "STRONG BUY", "#00c853"
            elif score >= 50: status, color = "HOLD / ACCUMULATE", "#ffab00"
            else: status, color = "AVOID / EXIT", "#d50000"

            # Mobile-friendly Header
            st.markdown(f"""
                <div style="background-color:{color}; padding:15px; border-radius:10px; text-align:center;">
                    <h1 style="color:white; margin:0;">{status}</h1>
                    <p style="color:white; margin:0; font-size:1.2em;">Score: {score}/100 | Horizon: {horizon} Months</p>
                </div>
            """, unsafe_allow_html=True)

            # Key Statistics
            st.write("### 📊 Market Snapshot")
            c1, c2, c3 = st.columns(3)
            c1.metric("Current Price", f"{current_price:,.2f}")
            c2.metric("Rel. Strength", f"{rs:+.1%}")
            c3.metric("RVOL", f"{df_final['RVOL'].iloc[-1]:.2f}")

            # Guidance Cards
            st.info(f"""
            **Guidance for {horizon}-month horizon:**
            - **Indicator Logic:** Using {f_ma} & {s_ma} day SMA for trend analysis.
            - **Target Exit:** {current_price*(1+(target_profit/100)):,.2f} (+{target_profit}%)
            - **Stop Loss:** {current_price*(1-(stop_loss/100)):,.2f} (-{stop_loss}%)
            - **ROE:** {info.get('returnOnEquity', 0):.2%} | **Debt/Equity:** {info.get('debtToEquity', 0)/100:.2f}
            """)

            # Horizon-Adjusted Charting
            # We show ~2x the horizon in the chart for context
            chart_lookback = horizon * 30 * 2 
            plot_df = df_final.tail(chart_lookback)
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['Close'], name="Price"))
            fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['Fast_MA'], name=f"{f_ma} SMA", line=dict(dash='dot')))
            fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['Slow_MA'], name=f"{s_ma} SMA", line=dict(width=2)))
            fig.update_layout(height=400, template="plotly_white", margin=dict(l=0, r=0, t=20, b=0), legend=dict(orientation="h", y=1.1))
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.error("Ticker not found. Remember: Use .NS for India (e.g., RELIANCE.NS)")

st.divider()
st.caption("Alpha Engine v2: Hybrid scoring adjusts automatically based on your intended holding period.")
