import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# --- SETTING UP THE ENGINE ---
class AlphaEngineV1:
    def __init__(self, ticker, target_pct, stop_pct, market):
        self.ticker = ticker.strip().upper()
        self.target_pct = target_pct / 100
        self.stop_pct = stop_pct / 100
        self.benchmark_ticker = "^GSPC" if market == "US" else "^NSEI"
        
    def get_data(self):
        # Fetching 1.5 years to ensure we have enough for SMA 200
        # multi_level_index=False flattens the headers and fixes your error
        df = yf.download(self.ticker, period="18mo", interval="1d", progress=False, multi_level_index=False)
        bench = yf.download(self.benchmark_ticker, period="18mo", interval="1d", progress=False, multi_level_index=False)
        
        if df.empty or bench.empty:
            return None, None, None
            
        info = yf.Ticker(self.ticker).info
        return df, bench, info

    def calculate_score(self, df, bench, info):
        # Ensure we are working with Series, not DataFrames
        close_price = df['Close']
        bench_close = bench['Close']

        # 1. Technical Indicators
        df['SMA50'] = close_price.rolling(50).mean()
        df['SMA200'] = close_price.rolling(200).mean()
        df['RVOL'] = df['Volume'] / df['Volume'].rolling(20).mean()
        
        # 2. Relative Strength (RS) Calculation
        # We calculate % change and take the last scalar value (.item()) to avoid label errors
        stock_ret_20 = ((close_price.iloc[-1] / close_price.iloc[-21]) - 1)
        bench_ret_20 = ((bench_close.iloc[-1] / bench_close.iloc[-21]) - 1)
        rs_value = stock_ret_20 - bench_ret_20
        
        # 3. Final Scoring Logic
        score = 0
        latest_close = close_price.iloc[-1]
        latest_sma50 = df['SMA50'].iloc[-1]
        latest_sma200 = df['SMA200'].iloc[-1]
        latest_rvol = df['RVOL'].iloc[-1]
        
        # Scoring Weightage
        if latest_close > latest_sma50: score += 30
        if latest_sma50 > latest_sma200: score += 20
        if rs_value > 0: score += 25
        if latest_rvol > 1.2: score += 15
        
        # Fundamentals (Safe check if key exists)
        growth = info.get('earningsQuarterlyGrowth')
        if growth is not None and growth > 0.1: 
            score += 10
        
        return round(score, 1), rs_value, latest_close, df

# --- STREAMLIT UI ---
st.set_page_config(page_title="Alpha Engine", layout="centered")

# Custom CSS for mobile-friendly view
st.markdown("""<style> .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 10px; } </style>""", unsafe_allow_html=True)

st.title("🚀 Alpha Engine v1")

# Sidebar
st.sidebar.header("Strategy Parameters")
market_type = st.sidebar.selectbox("Select Market", ["India", "US"])
default_ticker = "RELIANCE.NS" if market_type == "India" else "NVDA"
ticker_input = st.sidebar.text_input("Ticker Symbol", default_ticker)
target_profit = st.sidebar.slider("Target Profit (%)", 5, 20, 12)
stop_loss = st.sidebar.slider("Stop Loss (%)", 3, 10, 5)

if st.button("Run Deep Analysis"):
    with st.spinner(f'Evaluating {ticker_input}...'):
        engine = AlphaEngineV1(ticker_input, target_profit, stop_loss, market_type)
        df, bench, info = engine.get_data()
        
        if df is not None:
            score, rs, current_price, df_with_indicators = engine.calculate_score(df, bench, info)
            
            # Action Colors
            if score >= 75: color, action = "#00c853", "STRONG BUY"
            elif score >= 50: color, action = "#ffd600", "HOLD / WATCH"
            else: color, action = "#d50000", "AVOID / EXIT"

            # Result Header
            st.markdown(f"<div style='background-color:{color}; padding:20px; border-radius:10px; text-align:center;'>"
                        f"<h1 style='color:white; margin:0;'>{action}</h1>"
                        f"<p style='color:white; margin:0;'>Composite Score: {score}/100</p></div>", unsafe_allow_html=True)
            
            st.write("---")
            
            # Metrics
            c1, c2 = st.columns(2)
            c1.metric("Current Price", f"{current_price:.2f}")
            c2.metric("Relative Strength", f"{rs:+.2%}", delta_color="normal")

            # Trade Plan
            st.subheader("📍 Trade Plan")
            st.success(f"**Target Exit:** {current_price*(1+(target_profit/100)):.2f} (+{target_profit}%)")
            st.error(f"**Stop Loss:** {current_price*(1-(stop_loss/100)):.2f} (-{stop_loss}%)")

            # Charting
            st.subheader("Price Action")
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_with_indicators.index, y=df_with_indicators['Close'], name="Price", line=dict(color="#1f77b4")))
            fig.add_trace(go.Scatter(x=df_with_indicators.index, y=df_with_indicators['SMA50'], name="50-Day SMA", line=dict(dash='dot')))
            fig.update_layout(template="plotly_white", height=400, margin=dict(l=0, r=0, t=20, b=0), legend=dict(orientation="h", yanchor="bottom", y=1.02))
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.error("Invalid Ticker or Connection Issue. Ensure India tickers end with .NS (e.g., TCS.NS)")

st.caption("Alpha Engine utilizes Hybrid Technical/Fundamental Logic for medium-term guidance.")
