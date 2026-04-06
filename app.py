import streamlit as st
import pandas as pd
import numpy as np
import time
from finvizfinance.screener.overview import Overview
import warnings

# 1. INITIAL CONFIGURATION
warnings.filterwarnings("ignore")
st.set_page_config(page_title="7-14 Day Swing Launchpad", layout="wide")

# 2. UI: HEADER
st.title("🚀 7-14 Day Swing Launchpad")
st.info("""
**⚔️ SWING LAWS** | **YES**: All 3 Rules Pass | **MAYBE**: 2 Rules Pass | **DGNX**: Always Tracked.
""")

# 3. TECHNICAL UTILITIES
def calculate_rsi(series, window=14):
    try:
        delta = series.diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        ema_up = up.ewm(com=window-1, adjust=False).mean()
        ema_down = down.ewm(com=window-1, adjust=False).mean()
        rs = ema_up / (ema_down + 1e-9) # Prevent division by zero
        return 100 - (100 / (1 + rs))
    except: return 50

@st.cache_data(ttl=3600)
def fetch_and_analyze():
    # Define Column Schema upfront to prevent KeyErrors
    cols = ['Ticker', 'SIGNAL', 'Entry', 'TP (3.5x)', 'SL (1.5x)', 'RSI', 'RVOL', 'Score']
    
    try:
        f = Overview()
        f.set_filter(filters_dict={'Price': '$2 to $10'})
        all_tickers = f.screener_view()['Ticker'].tolist()
    except:
        all_tickers = ['DGNX', 'PLUG', 'NIO', 'MARA', 'RIOT']

    if 'DGNX' not in all_tickers: all_tickers.insert(0, 'DGNX')
    else:
        all_tickers.remove('DGNX'); all_tickers.insert(0, 'DGNX')

    pool = []
    dgnx_entry = None
    p_bar = st.progress(0)
    status = st.empty()
    
    # Scan limit to ensure we find candidates without timing out
    scan_limit = 200 
    
    for i, ticker in enumerate(all_tickers[:scan_limit]):
        status.text(f"🔍 Progress: {i}/{scan_limit} | Analyzing: {ticker}")
        
        try:
            url = f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d"
            df = pd.read_csv(url)
            if df.empty or len(df) < 60: continue

            df['Date'] = pd.to_datetime(df['Date'])
            df = df.sort_values('Date')

            # --- Technicals ---
            price = float(df['Close'].iloc[-1])
            sma_50 = float(df['Close'].rolling(window=50).mean().iloc[-1])
            
            df['TP_Calc'] = (df['High'] + df['Low'] + df['Close']) / 3
            df['PV'] = df['TP_Calc'] * df['Volume']
            vwap_20 = float(df['PV'].rolling(window=20).sum().iloc[-1] / (df['Volume'].rolling(window=20).sum().iloc[-1] + 1e-9))
            
            rvol = float(df['Volume'].iloc[-1] / (df['Volume'].rolling(window=60).mean().iloc[-1] + 1e-9))
            rsi = float(calculate_rsi(df['Close']).iloc[-1])
            
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
            
            setup = {
                'Ticker': ticker, 'SIGNAL': signal, 'Entry': round(price, 2),
                'TP (3.5x)': round(price + (3.5 * atr_14), 2), 'SL (1.5x)': round(price - (1.5 * atr_14), 2),
                'RSI': round(rsi, 1), 'RVOL': round(rvol, 2), 'Score': score
            }

            if ticker == 'DGNX': dgnx_entry = setup
            else: pool.append(setup)
            
            time.sleep(0.02)
        except: continue
        p_bar.progress((i + 1) / scan_limit)

    status.empty(); p_bar.empty()
    
    # 4. FINAL ASSEMBLY (SAFE VERSION)
    if not pool:
        # If nothing found, create an empty DF with correct columns
        df_all = pd.DataFrame(columns=cols)
    else:
        df_all = pd.DataFrame(pool)
    
    # Safely filter for YES and MAYBE
    yes_df = df_all[df_all['SIGNAL'] == 'YES'].sort_values('RVOL', ascending=False).head(5)
    maybe_df = df_all[df_all['SIGNAL'] == 'MAYBE'].sort_values('RVOL', ascending=False).head(10)
    
    final_results = pd.concat([yes_df, maybe_df])
    
    # Always ensure DGNX is present
    if dgnx_entry:
        d_df = pd.DataFrame([dgnx_entry])
        final_results = pd.concat([d_df, final_results]).drop_duplicates(subset='Ticker')
    
    # If truly everything is empty, return an empty DF with the column names so the UI doesn't break
    if final_results.empty:
        return pd.DataFrame(columns=cols)
        
    return final_results

# 5. EXECUTION
if st.button("🔍 EXECUTE TIERED SCAN", use_container_width=True):
    results = fetch_and_analyze()
    
    if not results.empty:
        def style_sig(val):
            if val == 'YES': return 'color: #00FFFF; font-weight: bold;'
            if val == 'MAYBE': return 'color: #FFA500; font-weight: bold;'
            return 'color: white;'

        st.dataframe(results.style.map(style_sig, subset=['SIGNAL']), width='stretch')
    else:
        st.warning("No matches found in the scan range. Market conditions may be too tight.")