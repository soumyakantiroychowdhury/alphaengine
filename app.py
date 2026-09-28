import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- SETTING UP THE ENGINE ---
class AlphaEngineV1:
    def __init__(self, ticker, target_pct, stop_pct, market):
        self.ticker = ticker
        self.target_pct = target_pct / 100
        self.stop_pct = stop_pct / 100
        self.benchmark = "^GSPC" if market == "US" else "^NSEI"
        
    def get_data(self):
        df = yf.download(self.ticker, period="1y", interval="1d", progress=False)
        bench = yf.download(self.benchmark, period="1y", interval="1d", progress=False)
        info = yf.Ticker(self.ticker).info
        return df, bench, info

    def calculate_score(self, df, bench, info):
        # Indicators
        df['SMA50'] = df['Close'].rolling(50).mean()
        df['SMA200'] = df['Close'].rolling(200).mean()
        df['RVOL'] = df['Volume'] / df['Volume'].rolling(20).mean()
        
        # RS Calculation
        stock_ret = df['Close'].pct_change(20).iloc[-1]
        bench_ret = bench['Close'].pct_change(20).iloc[-1]
        rs_value = stock_ret - bench_ret
        
        # Scoring
        score = 0
        latest = df.iloc[-1]
        
        if latest['Close'] > latest['SMA50']: score += 30
        if latest['SMA50'] > latest['SMA200']: score += 20
        if rs_value > 0: score += 25
        if latest['RVOL'] > 1.2: score += 15
        if info.get('earningsQuarterlyGrowth', 0) > 0.1: score += 10
        
        return round(score, 1), rs_value, latest

# --- STREAMLIT UI ---
st.set_page_config(page_title="Alpha Engine", layout="centered")

st.title("🚀 Alpha Engine v1")
st.subheader("Hybrid Stock Guidance System")

# Sidebar Inputs (Configurable Parameters)
st.sidebar.header("User Settings")
market_type = st.sidebar.selectbox("Select Market", ["India", "US"])
ticker_input = st.sidebar.text_input("Enter Ticker", "RELIANCE.NS" if market_type == "India" else "NVDA")
target_profit = st.sidebar.slider("Target Profit (%)", 5, 20, 12)
stop_loss = st.sidebar.slider("Stop Loss (%)", 3, 10, 5)

if st.button("Generate Guidance"):
    with st.spinner('Analyzing Market Factors...'):
        engine = AlphaEngineV1(ticker_input, target_profit, stop_loss, market_type)
        try:
            df, bench, info = engine.get_data()
            score, rs, latest = engine.calculate_score(df, bench, info)
            
            # Action Logic
            if score >= 75:
                color, action = "#00ff00", "STRONG BUY"
            elif score >= 50:
                color, action = "#ffa500", "HOLD / WATCH"
            else:
                color, action = "#ff4b4b", "AVOID / EXIT"

            # Dashboard Display
            st.markdown(f"<h1 style='text-align: center; color: {color};'>{action}</h1>", unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Engine Score", f"{score}/100")
            col2.metric("Current Price", f"{latest['Close']:.2f}")
            col3.metric("Rel. Strength", f"{rs:+.2%}")

            # Guidance Box
            st.info(f"""
            **Guidance for {ticker_input}:**
            - **Entry Zone:** {latest['Close']:.2f}
            - **Target Exit:** {latest['Close']*(1+(target_profit/100)):.2f} (+{target_profit}%)
            - **Stop Loss:** {latest['Close']*(1-(stop_loss/100)):.2f} (-{stop_loss}%)
            """)

            # Simple Chart
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name="Price"))
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA50'], name="SMA 50"))
            fig.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error(f"Error: {e}. Check if the ticker is correct.")

st.markdown("---")
st.caption("Strategic Guidance Only • Data: Yahoo Finance")
