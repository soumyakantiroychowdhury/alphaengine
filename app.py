import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# --- 1. CONFIGURATION & DATA ---

# Top 50 Lists (Simplified for performance)
NIFTY_50 = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "BHARTIARTL.NS", "INFY.NS", "ITC.NS", "SBIN.NS", "LICI.NS", "HINDUNILVR.NS", "LT.NS", "BAJFINANCE.NS", "HCLTECH.NS", "MARUTI.NS", "SUNPHARMA.NS", "ADANIENT.NS", "KOTAKBANK.NS", "TITAN.NS", "ULTRACEMCO.NS", "AXISBANK.NS", "NTPC.NS", "TATAMOTORS.NS", "ONGC.NS", "ADANIPORTS.NS", "ASIANPAINT.NS", "COALINDIA.NS", "BAJAJFINSV.NS", "BPCL.NS", "M&M.NS", "JSWSTEEL.NS", "TATASTEEL.NS", "HINDALCO.NS", "GRASIM.NS", "NESTLEIND.NS", "TECHM.NS", "BRITANNIA.NS", "CIPLA.NS", "EICHERMOT.NS", "POWERGRID.NS", "DIVISLAB.NS", "APOLLOHOSP.NS", "BAJAJ-AUTO.NS", "HEROMOTOCO.NS", "DRREDDY.NS", "WIPRO.NS", "SBILIFE.NS", "HDFCLIFE.NS", "INDUSINDBK.NS", "TATACONSUM.NS", "JIOFIN.NS"]
SP_50 = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "BRK-B", "TSLA", "LLY", "V", "UNH", "JPM", "AVGO", "MA", "XOM", "HD", "PG", "COST", "JNJ", "ORCL", "ADBE", "ABBV", "CVX", "CRM", "AMD", "BAC", "NFLX", "PEP", "WMT", "TMO", "KO", "MRK", "LIN", "WFC", "ACN", "DIS", "CSCO", "MCD", "ABT", "INTC", "INTU", "VZ", "CAT", "PFE", "CMCSA", "DHR", "IBM", "AMAT", "UBER", "UNP"]

# --- 2. ENGINE LOGIC ---

class AlphaEngineV4:
    def __init__(self, ticker, target, stop, market, horizon):
        self.ticker = ticker.strip().upper()
        self.target = target / 100
        self.stop = stop / 100
        self.horizon = horizon
        self.market = market
        self.bench = "^GSPC" if market == "US" else "^NSEI"

    @st.cache_data(ttl=3600) # Cache data for 1 hour
    def get_analysis_data(_self, ticker):
        period = "2y" if _self.horizon < 12 else "5y"
        df = yf.download(ticker, period=period, interval="1d", progress=False, multi_level_index=False)
        bench_df = yf.download(_self.bench, period=period, interval="1d", progress=False, multi_level_index=False)
        if df.empty: return None, None, None
        info = yf.Ticker(ticker).info
        return df, bench_df, info

    def process(self, df, bench_df, info):
        # MACD
        df['MACD'] = df['Close'].ewm(span=12).mean() - df['Close'].ewm(span=26).mean()
        df['Signal'] = df['MACD'].ewm(span=9).mean()
        df['Hist'] = df['MACD'] - df['Signal']

        # Adaptive SMA
        fast_p, slow_p = (20, 50) if self.horizon <= 4 else (50, 200)
        df['Fast_MA'] = df['Close'].rolling(fast_p).mean()
        df['Slow_MA'] = df['Close'].rolling(slow_p).mean()
        df['RVOL'] = df['Volume'] / df['Volume'].rolling(20).mean()

        # RS (Relative Strength)
        lookback = 21 if self.horizon <= 4 else 63
        s_ret = (df['Close'].iloc[-1] / df['Close'].iloc[-lookback]) - 1
        b_ret = (bench_df['Close'].iloc[-1] / bench_df['Close'].iloc[-lookback]) - 1
        rs_val = s_ret - b_ret

        # Scoring
        score = 0
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        if latest['Close'] > latest['Fast_MA']: score += 20
        if latest['Fast_MA'] > latest['Slow_MA']: score += 20
        if latest['MACD'] > latest['Signal']: score += 15
        if latest['Hist'] > prev['Hist']: score += 15
        if rs_val > 0: score += 20
        if info.get('returnOnEquity', 0) > 0.15: score += 10
        
        return round(score), rs_val, latest, fast_p, slow_p

# --- 3. STREAMLIT APP & NAVIGATION ---

st.set_page_config(page_title="Alpha Engine v4", layout="wide")

# Global Session State
if 'current_ticker' not in st.session_state:
    st.session_state.current_ticker = "NVDA"

# Sidebar - Global Settings
st.sidebar.title("🛠️ Settings")
market_choice = st.sidebar.selectbox("Market", ["US", "India"])
horizon = st.sidebar.slider("Horizon (Months)", 1, 24, 3)
target = st.sidebar.number_input("Target Profit %", 5, 50, 12)
stop = st.sidebar.number_input("Stop Loss %", 3, 20, 5)

page = st.sidebar.radio("Navigation", ["Deep Analysis", "Top 50 Leaderboard"])

# Initialize Engine
engine = AlphaEngineV4(st.session_state.current_ticker, target, stop, market_choice, horizon)

# --- PAGE 1: DEEP ANALYSIS ---

if page == "Deep Analysis":
    st.title("🔬 Deep Analysis")
    ticker_input = st.text_input("Analyze Specific Ticker:", st.session_state.current_ticker)
    
    if st.button("Run Engine"):
        st.session_state.current_ticker = ticker_input
        df, bench, info = engine.get_analysis_data(ticker_input)
        
        if df is not None:
            score, rs, latest, f_ma, s_ma = engine.process(df, bench, info)
            
            # Action Banner
            color = "#00c853" if score >= 80 else ("#ffab00" if score >= 55 else "#d50000")
            st.markdown(f"<div style='background-color:{color}; padding:20px; border-radius:10px; text-align:center; color:white;'>"
                        f"<h1>{st.session_state.current_ticker}: {score}/100</h1></div>", unsafe_allow_html=True)

            # RESTORED: Market Snapshot
            st.write("### 💹 Market Snapshot")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Current Price", f"{latest['Close']:,.2f}")
            m2.metric("Relative Strength", f"{rs:+.2%}")
            m3.metric("RVOL (Volume)", f"{latest['RVOL']:.2f}")
            m4.metric("MACD Pulse", "Bullish" if latest['Hist'] > 0 else "Bearish")

            # Momentum Info
            st.info(f"**Engine Logic:** Using {f_ma}/{s_ma} SMA for a {horizon}-month horizon. MACD Signal is currently **{'Confirmed' if latest['Hist'] > 0 else 'Fading'}**.")

            # Charts
            c1, c2 = st.columns(2)
            with c1:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df.index[-100:], y=df['Close'].tail(100), name="Price"))
                fig.add_trace(go.Scatter(x=df.index[-100:], y=df['Fast_MA'].tail(100), name="Fast MA", line=dict(dash='dot')))
                fig.update_layout(title="Price Action", template="plotly_white")
                st.plotly_chart(fig, use_container_width=True)
            with c2:
                fig_m = go.Figure()
                fig_m.add_trace(go.Bar(x=df.index[-100:], y=df['Hist'].tail(100), name="MACD Hist"))
                fig_m.update_layout(title="Momentum Intensity (MACD)", template="plotly_white")
                st.plotly_chart(fig_m, use_container_width=True)

            # Trade Plan
            st.subheader("📍 Trade Execution Plan")
            p1, p2 = st.columns(2)
            p1.success(f"**Target Exit (+{target}%):** {latest['Close']*(1+target/100):,.2f}")
            p2.error(f"**Stop Loss (-{stop}%):** {latest['Close']*(1-stop/100):,.2f}")

# --- PAGE 2: LEADERBOARD ---

elif page == "Top 50 Leaderboard":
    st.title(f"🏆 Top 50 Momentum Leaderboard ({market_choice})")
    st.write("Ranking stocks based on Trend, MACD Pulse, and Relative Strength.")
    
    ticker_list = SP_50 if market_choice == "US" else NIFTY_50
    leaderboard_data = []

    if st.button("Scan Market (This takes ~30 seconds)"):
        progress_bar = st.progress(0)
        for i, t in enumerate(ticker_list):
            try:
                # Optimized minimal fetch for scanning
                df = yf.download(t, period="1y", interval="1d", progress=False, multi_level_index=False)
                bench_df = yf.download(engine.bench, period="1y", interval="1d", progress=False, multi_level_index=False)
                score, rs, latest, _, _ = engine.process(df, bench_df, {}) # Pass empty dict for speed
                
                leaderboard_data.append({
                    "Ticker": t,
                    "Score": score,
                    "Price": round(latest['Close'], 2),
                    "RS %": f"{rs:+.2%}",
                    "Status": "Strong Buy" if score >= 80 else ("Hold" if score >= 55 else "Avoid")
                })
            except:
                continue
            progress_bar.progress((i + 1) / len(ticker_list))

        # Create Table
        result_df = pd.DataFrame(leaderboard_data).sort_values(by="Score", ascending=False)
        st.dataframe(result_df, use_container_width=True, height=600)
        
        st.success("Scan Complete. Copy a ticker from above and paste it in 'Deep Analysis' for the full report.")
