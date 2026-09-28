import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# --- HYBRID ALPHA ENGINE V3 (Momentum & Horizon Integrated) ---
class AlphaEngineV3:
    def __init__(self, ticker, target_pct, stop_loss_pct, market, horizon_months):
        self.ticker = ticker.strip().upper()
        self.target_pct = target_pct / 100
        self.stop_pct = stop_loss_pct / 100
        self.horizon = horizon_months
        self.benchmark_ticker = "^GSPC" if market == "US" else "^NSEI"
        
    def get_data(self):
        # Fetching enough history for long-term indicators
        period = "2y" if self.horizon < 12 else "5y"
        df = yf.download(self.ticker, period=period, interval="1d", progress=False, multi_level_index=False)
        bench = yf.download(self.benchmark_ticker, period=period, interval="1d", progress=False, multi_level_index=False)
        
        if df.empty or bench.empty:
            return None, None, None
            
        info = yf.Ticker(self.ticker).info
        return df, bench, info

    def calculate_indicators(self, df, bench):
        # 1. MACD CALCULATION (The "Pulse")
        # Standard: 12-day EMA, 26-day EMA, 9-day Signal
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['Signal_Line']

        # 2. HORIZON-ADAPTIVE SMA (The "Skeleton")
        if self.horizon <= 4:
            fast, slow = 20, 50
            rs_lookback = 21 
        elif self.horizon <= 12:
            fast, slow = 50, 100
            rs_lookback = 63
        else:
            fast, slow = 50, 200
            rs_lookback = 126

        df['Fast_MA'] = df['Close'].rolling(fast).mean()
        df['Slow_MA'] = df['Close'].rolling(slow).mean()
        
        # 3. RELATIVE STRENGTH
        stock_ret = ((df['Close'].iloc[-1] / df['Close'].iloc[-rs_lookback]) - 1)
        bench_ret = ((bench['Close'].iloc[-1] / bench['Close'].iloc[-rs_lookback]) - 1)
        rs_value = stock_ret - bench_ret
        
        return df, rs_value, fast, slow

    def get_score(self, df, rs_value, info):
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        score = 0
        
        # A. TREND COMPONENT (40%)
        if latest['Close'] > latest['Fast_MA']: score += 20
        if latest['Fast_MA'] > latest['Slow_MA']: score += 20
        
        # B. MACD MOMENTUM COMPONENT (30%) - RESTORED
        # Bullish if MACD is above Signal Line AND Histogram is increasing
        if latest['MACD'] > latest['Signal_Line']: score += 15
        if latest['MACD_Hist'] > prev['MACD_Hist']: score += 15
        
        # C. RELATIVE STRENGTH (20%)
        if rs_value > 0: score += 20
        
        # D. FUNDAMENTAL QUALITY (10%)
        roe = info.get('returnOnEquity', 0)
        if roe > 0.15: score += 10
        
        return score

# --- UI LAYER ---
st.set_page_config(page_title="Alpha Engine v3", layout="centered")
st.title("🚀 Alpha Engine v3")
st.markdown("#### Precision Momentum + Horizon Logic")

# Sidebar
st.sidebar.header("User Settings")
market = st.sidebar.selectbox("Market", ["India", "US"])
ticker = st.sidebar.text_input("Ticker", "RELIANCE.NS" if market == "India" else "NVDA")
horizon = st.sidebar.slider("Investment Horizon (Months)", 1, 24, 3)
target = st.sidebar.number_input("Target Profit %", 5, 50, 12)
stop = st.sidebar.number_input("Stop Loss %", 3, 20, 5)

if st.button("Generate Guidance"):
    with st.spinner("Decoding Momentum Signals..."):
        engine = AlphaEngineV3(ticker, target, stop, market, horizon)
        df, bench, info = engine.get_data()
        
        if df is not None:
            df, rs, f_ma, s_ma = engine.calculate_indicators(df, bench)
            score = engine.get_score(df, rs, info)
            
            latest = df.iloc[-1]
            price = latest['Close']
            
            # Action Colors
            if score >= 80: action, color = "STRONG BUY", "#00c853"
            elif score >= 55: action, color = "HOLD / WATCH", "#ffab00"
            else: action, color = "AVOID / EXIT", "#d50000"

            # Result Dashboard
            st.markdown(f"<div style='background-color:{color}; padding:20px; border-radius:10px; text-align:center;'>"
                        f"<h1 style='color:white; margin:0;'>{action}</h1>"
                        f"<p style='color:white; margin:0;'>Score: {score}/100 | MACD Confirmed: {'YES' if latest['MACD_Hist'] > 0 else 'NO'}</p></div>", unsafe_allow_html=True)

            # Key Statistics
            st.write("### 📊 Market Snapshot")
            c1, c2, c3 = st.columns(3)
            c1.metric("Current Price", f"{current_price:,.2f}")
            c2.metric("Rel. Strength", f"{rs:+.1%}")
            c3.metric("RVOL", f"{df_final['RVOL'].iloc[-1]:.2f}")
            # The "No Emotional Bias" Section
            st.write("### 🧠 Momentum Insight")
            macd_status = "Accelerating" if latest['MACD_Hist'] > df['MACD_Hist'].iloc[-2] else "Decelerating"
            st.info(f"The MACD Histogram is **{macd_status}**. This proves that the current price movement has **{'Real' if score > 70 else 'Weak'}** momentum behind it.")

            # Charts
            # 1. Price + SMA
            fig_price = go.Figure()
            plot_df = df.tail(horizon * 30 + 60)
            fig_price.add_trace(go.Scatter(x=plot_df.index, y=plot_df['Close'], name="Price"))
            fig_price.add_trace(go.Scatter(x=plot_df.index, y=plot_df['Fast_MA'], name=f"{f_ma} SMA", line=dict(dash='dot')))
            fig_price.update_layout(height=300, template="plotly_white", margin=dict(l=0, r=0, t=20, b=0))
            st.plotly_chart(fig_price, use_container_width=True)

            # 2. MACD Histogram (The "Engine Room")
            fig_macd = go.Figure()
            fig_macd.add_trace(go.Bar(x=plot_df.index, y=plot_df['MACD_Hist'], name="MACD Histogram", marker_color='gray'))
            fig_macd.update_layout(height=200, template="plotly_white", margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig_macd, use_container_width=True)

            # Trade Plan
            st.write("---")
            c1, c2 = st.columns(2)
            c1.success(f"**Target:** {price*(1+(target/100)):,.2f}")
            c2.error(f"**Stop:** {price*(1-(stop/100)):,.2f}")
        else:
            st.error("Data fetch failed. Check ticker symbol.")
