import streamlit as st
import pandas as pd
import numpy as np
import time
from finvizfinance.screener.overview import Overview
import warnings

# 1. INITIAL CONFIGURATION
warnings.filterwarnings("ignore")
st.set_page_config(page_title="7-14 Day Swing Launchpad", layout="wide")

# 2. UI: HEADER & RULES
st.title("🚀 7-14 Day Swing Launchpad")
st.info("""
**⚔️ RUTHLESS SWING LAWS (7-14 DAY WINDOW)**
1. **Trend:** Price > 20D Rolling VWAP AND Price > 50D SMA.
2. **Momentum:** RSI(14) between 45 and 60 (The Launchpad).
3. **Fuel:** RVOL > 1.5 (Institutional Accumulation).
4. **Execution:** 5 setups max | Exit: 3.5x ATR Profit / 1.5x ATR Stop.
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
    # A. Get Universe from Finviz ($2 - $10)
    try:
        f = Overview()
        f.set_filter(filters_dict={'Price': '$2 to $10'})
        all_tickers = f.screener_view()['Ticker'].tolist()
    except:
        all_tickers = ['PLUG', 'NIO', 'MARA', 'RIOT', 'F', 'AMD'] # Emergency fallback

    # B. DGNX Priority Injection
    if 'DGNX' not in all_tickers: all_tickers.insert(0, 'DGNX')
    else:
        all_tickers.remove('DGNX')
        all_tickers.insert(0, 'DGNX')

    found_setups = []
    dgnx_entry = None
    p_bar = st.progress(0)
    status = st.empty()
    
    # C. Processing Loop
    for i, ticker in enumerate(all_tickers):
        if len(found_setups) >= 5 and dgnx_entry is not None:
            break
        
        status.text(f"Scanning Ticker {i}/{len(all_tickers)}: {ticker} | Found: {len(found_setups)}/5")
        
        try:
            # DIRECT STOOQ FETCH (CSV Bypass for Rate Limits)
            url = f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d"
            df = pd.read_csv(url)
            
            if df.empty or len(df) < 60:
                continue

            # Data Cleaning
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.sort_values('Date')

            # --- Technical Engine ---
            price = float(df['Close'].iloc[-1])
            sma_50 = float(df['Close'].rolling(window=50).mean().iloc[-1])
            
            # 20D VWAP Calculation
            df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
            df['PV'] = df['TP'] * df['Volume']
            vwap_20 = float(df['PV'].rolling(window=20).sum().iloc[-1] / df['Volume'].rolling(window=20).sum().iloc[-1])
            
            # RSI & RVOL
            rvol = float(df['Volume'].iloc[-1] / df['Volume'].rolling(window=60).mean().iloc[-1])
            rsi = float(calculate_rsi(df['Close']).iloc[-1])
            
            # ATR(14) for Stop/Target
            tr = pd.concat([df['High'] - df['Low'], 
                            (df['High'] - df['Close'].shift()).abs(), 
                            (df['Low'] - df['Close'].shift()).abs()], axis=1).max(axis=1)
            atr_14 = float(tr.rolling(window=14).mean().iloc[-1])

            # --- The Launchpad Logic ---
            is_buy = "YES" if (price > vwap_20 and price > sma_50 and 45 <= rsi <= 60 and rvol > 1.5) else "NO"
            
            setup = {
                'Ticker': ticker, 'BUY': is_buy, 'Entry': round(price, 2),
                'TP (3.5x)': round(price + (3.5 * atr_14), 2), 'SL (1.5x)': round(price - (1.5 * atr_14), 2),
                '20D VWAP': round(vwap_20, 2), '50D SMA': round(sma_50, 2), 'RSI': round(rsi, 1),
                'RVOL': round(rvol, 2), '60D Avg Vol': int(df['Volume'].tail(60).mean())
            }

            if ticker == 'DGNX': dgnx_entry = setup
            if is_buy == "YES": found_setups.append(setup)
            
            time.sleep(0.05) # Pulse delay to prevent server block

        except:
            continue
            
        p_bar.progress(min((i + 1) / len(all_tickers), 1.0))

    status.empty()
    p_bar.empty()
    
    # D. Final Sorting & Merging
    final_list = found_setups
    if dgnx_entry and not any(s['Ticker'] == 'DGNX' for s in final_list):
        final_list.append(dgnx_entry)
        
    df_result = pd.DataFrame(final_list)
    if not df_result.empty:
        df_result = df_result.sort_values(by=['BUY', 'RVOL'], ascending=[False, False]).head(6)
    return df_result

# 4. APP EXECUTION
if st.button("🔍 EXECUTE RUTHLESS SCAN", use_container_width=True):
    results = fetch_and_analyze()
    if not results.empty:
        # Styling: Highlighting the BUY column in Electric Blue
        st.dataframe(
            results.style.map(lambda x: 'color: #00FFFF; font-weight: bold;' if x == 'YES' else 'color: white;', subset=['BUY']),
            width='stretch'
        )
    else:
        st.error("No setups found. The market might be in a cool-down phase.")