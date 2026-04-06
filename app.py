import streamlit as st
import yfinance as yf
import pandas as pd
from finvizfinance.screener.overview import Overview
import numpy as np
import time
import warnings

# Quant-level configuration
warnings.filterwarnings("ignore")
st.set_page_config(page_title="Resilient Swing Launchpad", layout="wide")

# UI: CSS for Clean Table & Visual Priority
st.markdown("""
    <style>
    .stDataFrame div[data-testid="stTable"] { overflow: visible !important; }
    .stDataFrame [data-testid="styled-data-frame"] { height: auto !important; }
    [data-testid="stMetricValue"] { font-size: 1.5rem !important; }
    </style>
    """, unsafe_allow_html=True)

# UI: Header Reminders
st.title("🚀 Resilient 7-14 Day Swing Launchpad")
st.info("""
**⚔️ 7-14 DAY SWING LAWS**
1. **TREND:** Price > 20D Rolling VWAP AND Price > 50D SMA.
2. **MOMENTUM:** RSI(14) between 45 and 60 (The Launchpad).
3. **FUEL:** RVOL > 1.5 (Institutional Accumulation).
4. **EXIT:** 3.5x ATR Profit Target | 1.5x ATR Safety Stop.
""")

def sanitize_ticker(ticker):
    return ticker.replace('-', '.')

def calculate_rsi(data, window=14):
    delta = data.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=window-1, adjust=False).mean()
    ema_down = down.ewm(com=window-1, adjust=False).mean()
    rs = ema_up / ema_down
    return 100 - (100 / (1 + rs))

@st.cache_data(ttl=3600)
def fetch_launchpad_data():
    try:
        f = Overview()
        f.set_filter(filters_dict={'Price': '$2 to $10'})
        full_df = f.screener_view()
        all_tickers = full_df['Ticker'].tolist()
    except:
        all_tickers = ['PLUG', 'NIO', 'MARA', 'RIOT', 'F', 'AMD', 'PFE', 'AAL']

    # Ensure DGNX is first in the queue
    if 'DGNX' not in all_tickers: all_tickers.insert(0, 'DGNX')
    else:
        all_tickers.remove('DGNX')
        all_tickers.insert(0, 'DGNX')

    found_setups = []
    dgnx_entry = None
    
    p_bar = st.progress(0)
    status = st.empty()
    error_log = st.sidebar.expander("⚠️ Connection Logs", expanded=False)
    
    # We scan until we hit our quota or exhaust the universe
    for i, ticker in enumerate(all_tickers):
        if len(found_setups) >= 5 and dgnx_entry is not None:
            break
        
        status.text(f"Searching for 5 'YES' signals... Found: {len(found_setups)}/5 | Scanning: {ticker}")
        y_ticker = sanitize_ticker(ticker)
        
        # Meticulous error handling to bypass Rate Limits
        try:
            # Added small sleep to respect Yahoo's Rate Limit
            time.sleep(0.2) 
            
            df = yf.download(y_ticker, period="1y", interval="1d", progress=False, threads=False)
            
            if df.empty or len(df) < 60:
                continue

            # --- Technical Calculations ---
            price = float(df['Close'].iloc[-1])
            sma_50 = float(df['Close'].rolling(window=50).mean().iloc[-1])
            
            df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
            df['PV'] = df['TP'] * df['Volume']
            vwap_20 = float(df['PV'].rolling(window=20).sum().iloc[-1] / df['Volume'].rolling(window=20).sum().iloc[-1])
            
            avg_vol_60 = float(df['Volume'].rolling(window=60).mean().iloc[-1])
            rvol = float(df['Volume'].iloc[-1] / avg_vol_60)
            rsi = float(calculate_rsi(df['Close']).iloc[-1])
            
            # ATR Logic for Exits
            high_low = df['High'] - df['Low']
            tr = pd.concat([high_low, np.abs(df['High'] - df['Close'].shift()), np.abs(df['Low'] - df['Close'].shift())], axis=1).max(axis=1)
            atr_14 = float(tr.rolling(window=14).mean().iloc[-1])

            # --- Triple-Filter Logic ---
            is_buy = "YES" if (price > vwap_20 and price > sma_50 and 45 <= rsi <= 60 and rvol > 1.5) else "NO"
            
            setup = {
                'Ticker': ticker, 'BUY (YES)': is_buy, 'Entry': round(price, 2),
                'Take Profit': round(price + (3.5 * atr_14), 2), 'Stop Loss': round(price - (1.5 * atr_14), 2),
                '20D VWAP': round(vwap_20, 2), '50D SMA': round(sma_50, 2), 'RSI': round(rsi, 1),
                'RVOL': round(rvol, 2), '60D Avg Vol': int(avg_vol_60)
            }

            if ticker == 'DGNX':
                dgnx_entry = setup
            
            if is_buy == "YES" and len(found_setups) < 5:
                found_setups.append(setup)

        except Exception as e:
            error_log.write(f"Skipped {ticker}: Rate limited or Data error.")
            continue
            
        p_bar.progress(min((i + 1) / len(all_tickers), 1.0))

    status.empty()
    p_bar.empty()

    # Final Merge
    all_final = found_setups
    if dgnx_entry and not any(s['Ticker'] == 'DGNX' for s in all_final):
        all_final.append(dgnx_entry)
        
    res_df = pd.DataFrame(all_final)
    if not res_df.empty:
        # Prioritize BUY=YES then highest RVOL
        res_df = res_df.sort_values(by=['BUY (YES)', 'RVOL'], ascending=[False, False])
    return res_df

if st.button("🔍 EXECUTE RUTHLESS SCAN", use_container_width=True):
    data = fetch_launchpad_data()
    
    if not data.empty:
        def style_logic(val):
            return 'color: #00FFFF; font-weight: bold;' if val == 'YES' else 'color: white;'

        st.dataframe(
            data.style.map(style_logic, subset=['BUY (YES)']),
            width='stretch',
            height=400
        )
    else:
        st.error("Severe Rate Limiting detected. Yahoo Finance is blocking requests. Wait 5 minutes and try again.")