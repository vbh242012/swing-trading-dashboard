import streamlit as st
import pandas as pd
import numpy as np
import time
from finvizfinance.screener.overview import Overview
import warnings

# 1. INITIAL CONFIGURATION
warnings.filterwarnings("ignore")
st.set_page_config(page_title="7-14 Day Tiered Launchpad", layout="wide")

# 2. UI: HEADER & RULES
st.title("🚀 7-14 Day Swing Launchpad (Tiered)")
st.info("""
**⚔️ SWING SCORING SYSTEM**
* **YES:** Price > VWAP/SMA **AND** RSI 45-60 **AND** RVOL > 1.5.
* **MAYBE:** Price > VWAP/SMA **AND** (Either RSI 45-60 OR RVOL > 1.5).
* **DGNX:** Always displayed for tracking.
""")

# 3. TECHNICAL UTILITIES
def calculate_rsi(series, window=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=window-1, adjust=False).mean()
    ema_down = down.ewm(com=window-1, adjust=False).mean()
    rs = ema_up / ema_down
    return 100 - (100 / (1 + rs))

@st.cache_data(ttl=3600)
def fetch_and_analyze():
    try:
        f = Overview()
        f.set_filter(filters_dict={'Price': '$2 to $10'})
        all_tickers = f.screener_view()['Ticker'].tolist()
    except:
        all_tickers = ['PLUG', 'NIO', 'MARA', 'RIOT', 'F', 'AMD']

    # DGNX Priority
    if 'DGNX' not in all_tickers: all_tickers.insert(0, 'DGNX')
    else:
        all_tickers.remove('DGNX'); all_tickers.insert(0, 'DGNX')

    pool = []
    dgnx_entry = None
    p_bar = st.progress(0)
    status = st.empty()
    
    # We scan a larger chunk to ensure we fill the "Maybe" slots
    scan_limit = 300 
    
    for i, ticker in enumerate(all_tickers[:scan_limit]):
        status.text(f"Scanning Ticker {i}/{scan_limit}: {ticker} | Pool Size: {len(pool)}")
        
        try:
            url = f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d"
            df = pd.read_csv(url)
            if df.empty or len(df) < 60: continue

            df['Date'] = pd.to_datetime(df['Date'])
            df = df.sort_values('Date')

            # --- Technical Engine ---
            price = float(df['Close'].iloc[-1])
            sma_50 = float(df['Close'].rolling(window=50).mean().iloc[-1])
            
            df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
            df['PV'] = df['TP'] * df['Volume']
            vwap_20 = float(df['PV'].rolling(window=20).sum().iloc[-1] / df['Volume'].rolling(window=20).sum().iloc[-1])
            
            rvol = float(df['Volume'].iloc[-1] / df['Volume'].rolling(window=60).mean().iloc[-1])
            rsi = float(calculate_rsi(df['Close']).iloc[-1])
            
            tr = pd.concat([df['High'] - df['Low'], (df['High'] - df['Close'].shift()).abs(), (df['Low'] - df['Close'].shift()).abs()], axis=1).max(axis=1)
            atr_14 = float(tr.rolling(window=14).mean().iloc[-1])

            # --- Tiered Logic ---
            rule_trend = (price > vwap_20 and price > sma_50)
            rule_mom = (45 <= rsi <= 60)
            rule_fuel = (rvol > 1.5)
            
            # Scoring
            score = sum([rule_trend, rule_mom, rule_fuel])
            
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
            
            time.sleep(0.05)

        except: continue
        p_bar.progress((i + 1) / scan_limit)

    status.empty(); p_bar.empty()
    
    # Sorting Logic:
    # 1. YES signals first
    # 2. MAYBE signals second
    # 3. Sort both by RVOL descending
    df_all = pd.DataFrame(pool)
    
    yes_df = df_all[df_all['SIGNAL'] == 'YES'].sort_values('RVOL', ascending=False).head(5)
    maybe_df = df_all[df_all['SIGNAL'] == 'MAYBE'].sort_values('RVOL', ascending=False).head(10)
    
    # Merge and add DGNX
    final_results = pd.concat([yes_df, maybe_df])
    if dgnx_entry:
        dgnx_df = pd.DataFrame([dgnx_entry])
        final_results = pd.concat([dgnx_df, final_results]).drop_duplicates(subset='Ticker')
        
    return final_results

# 4. APP EXECUTION
if st.button("🔍 EXECUTE TIERED SCAN", use_container_width=True):
    results = fetch_and_analyze()
    if not results.empty:
        def color_signal(val):
            if val == 'YES': return 'color: #00FFFF; font-weight: bold;'
            if val == 'MAYBE': return 'color: #FFA500; font-weight: bold;' # Orange
            return 'color: white;'

        st.dataframe(results.style.map(color_signal, subset=['SIGNAL']), width='stretch')
    else:
        st.error("Connection error. Try again in 60 seconds.")