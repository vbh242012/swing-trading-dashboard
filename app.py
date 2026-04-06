import streamlit as st
import pandas as pd
import numpy as np
import time
from finvizfinance.screener.overview import Overview
import warnings

# 1. CONFIG
warnings.filterwarnings("ignore")
st.set_page_config(page_title="7-14 Day Swing Launchpad", layout="wide")

# 2. UI: HEADER
st.title("🚀 7-14 Day Swing Launchpad")
st.info("""
**⚔️ SWING LAWS** | **YES**: All 3 Rules Pass | **MAYBE**: 2 Rules Pass | **DGNX**: Priority Tracking.
""")

def calculate_rsi(series, window=14):
    try:
        delta = series.diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        ema_up = up.ewm(com=window-1, adjust=False).mean()
        ema_down = down.ewm(com=window-1, adjust=False).mean()
        rs = ema_up / (ema_down + 1e-9)
        return 100 - (100 / (1 + rs))
    except: return pd.Series([50] * len(series))

def process_ticker(ticker):
    """Core logic to fetch and score a single ticker."""
    try:
        # Direct Stooq CSV Link
        url = f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d"
        df = pd.read_csv(url)
        if df.empty or len(df) < 60:
            return None

        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date')

        # --- Technicals ---
        price = float(df['Close'].iloc[-1])
        sma_50 = float(df['Close'].rolling(window=50).mean().iloc[-1])
        
        df['TP_Calc'] = (df['High'] + df['Low'] + df['Close']) / 3
        df['PV'] = df['TP_Calc'] * df['Volume']
        vwap_20 = float(df['PV'].rolling(window=20).sum().iloc[-1] / (df['Volume'].rolling(window=20).sum().iloc[-1] + 1e-9))
        
        rvol = float(df['Volume'].iloc[-1] / (df['Volume'].rolling(window=60).mean().iloc[-1] + 1e-9))
        rsi_series = calculate_rsi(df['Close'])
        rsi = float(rsi_series.iloc[-1])
        
        tr = pd.concat([df['High'] - df['Low'], (df['High'] - df['Close'].shift()).abs(), (df['Low'] - df['Close'].shift()).abs()], axis=1).max(axis=1)
        atr_14 = float(tr.rolling(window=14).mean().iloc[-1])

        # --- Scoring ---
        r1 = 1 if (price > vwap_20 and price > sma_50) else 0
        r2 = 1 if (45 <= rsi <= 60) else 0
        r3 = 1 if (rvol > 1.5) else 0
        score = r1 + r2 + r3
        
        signal = "NO"
        if score == 3: signal = "YES"
        elif score == 2: signal = "MAYBE"
        
        return {
            'Ticker': ticker, 'SIGNAL': signal, 'Entry': round(price, 2),
            'TP (3.5x)': round(price + (3.5 * atr_14), 2), 'SL (1.5x)': round(price - (1.5 * atr_14), 2),
            'RSI': round(rsi, 1), 'RVOL': round(rvol, 2), 'Score': score
        }
    except:
        return None

@st.cache_data(ttl=3600)
def fetch_and_analyze():
    cols = ['Ticker', 'SIGNAL', 'Entry', 'TP (3.5x)', 'SL (1.5x)', 'RSI', 'RVOL', 'Score']
    
    # --- 1. FORCE DGNX FIRST ---
    dgnx_data = process_ticker('DGNX')
    if not dgnx_data:
        # If Stooq fails, create a placeholder so it ALWAYS shows up
        dgnx_data = {col: "DATA ERROR" for col in cols}
        dgnx_data['Ticker'] = 'DGNX'
        dgnx_data['SIGNAL'] = 'N/A'

    # --- 2. GET REST OF UNIVERSE ---
    try:
        f = Overview()
        f.set_filter(filters_dict={'Price': '$2 to $10'})
        all_tickers = f.screener_view()['Ticker'].tolist()
    except:
        all_tickers = []

    pool = []
    p_bar = st.progress(0)
    status = st.empty()
    scan_limit = 150 # Faster scan to avoid timeouts
    
    for i, ticker in enumerate(all_tickers[:scan_limit]):
        if ticker == 'DGNX': continue
        status.text(f"🔍 Scanning: {ticker} ({i}/{scan_limit})")
        
        res = process_ticker(ticker)
        if res: pool.append(res)
        
        time.sleep(0.02)
        p_bar.progress((i + 1) / scan_limit)

    status.empty(); p_bar.empty()
    
    # --- 3. ASSEMBLY ---
    df_pool = pd.DataFrame(pool if pool else [], columns=cols)
    
    yes_df = df_pool[df_pool['SIGNAL'] == 'YES'].sort_values('RVOL', ascending=False).head(5)
    maybe_df = df_pool[df_pool['SIGNAL'] == 'MAYBE'].sort_values('RVOL', ascending=False).head(10)
    
    # Create final DF starting with DGNX
    dgnx_df = pd.DataFrame([dgnx_data])
    final_results = pd.concat([dgnx_df, yes_df, maybe_df]).reset_index(drop=True)
    
    return final_results

# 4. EXECUTION
if st.button("🔍 EXECUTE RUTHLESS SCAN", use_container_width=True):
    results = fetch_and_analyze()
    
    def style_sig(val):
        if val == 'YES': return 'color: #00FFFF; font-weight: bold;'
        if val == 'MAYBE': return 'color: #FFA500; font-weight: bold;'
        if val == 'N/A' or val == 'DATA ERROR': return 'color: #FF4B4B;'
        return 'color: white;'

    st.dataframe(results.style.map(style_sig, subset=['SIGNAL']), width='stretch')