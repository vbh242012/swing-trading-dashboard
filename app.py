import streamlit as st
import yfinance as yf
import pandas as pd
from finvizfinance.screener.overview import Overview
import numpy as np
import warnings

warnings.filterwarnings("ignore")

st.set_page_config(page_title="7-14 Day Swing Tiered", layout="wide")

# CSS for a clean, flat dashboard look
st.markdown("""
    <style>
    .stDataFrame div[data-testid="stTable"] { overflow: visible !important; }
    .stDataFrame [data-testid="styled-data-frame"] { height: auto !important; }
    </style>
    """, unsafe_allow_html=True)

# --- HEADER RULES ---
st.title("🚀 7-14 Day Swing Launchpad (Tiered)")

st.info("""
**⚔️ SWING SCORING LOGIC**
1. **YES (3/3):** Price > VWAP/SMA **AND** RSI 45-60 **AND** RVOL > 1.5.
2. **MAYBE (2/3):** Any two of the above conditions met.
3. **DGNX:** Always tracked regardless of score.
""")

def format_ticker(t):
    return t.replace('-', '.')

def calculate_rsi(series, window=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=window-1, adjust=False).mean()
    ema_down = down.ewm(com=window-1, adjust=False).mean()
    rs = ema_up / (ema_down + 1e-9)
    return 100 - (100 / (1 + rs))

@st.cache_data(ttl=3600)
def get_tiered_swing_data():
    try:
        f = Overview()
        f.set_filter(filters_dict={'Price': '$2 to $10'})
        tickers = f.screener_view()['Ticker'].tolist()
    except:
        tickers = ['DGNX', 'PLUG', 'NIO', 'F', 'AAL']
    
    # Force DGNX to the front
    if 'DGNX' not in tickers: tickers.insert(0, 'DGNX')
    else:
        tickers.remove('DGNX'); tickers.insert(0, 'DGNX')

    results = []
    p = st.progress(0)
    status = st.empty()

    # Scan up to 250 tickers to find enough quality "Maybe" setups
    scan_limit = 250 
    
    for i, t in enumerate(tickers[:scan_limit]):
        # Target: 5 YES and 10 MAYBE
        yes_found = [r for r in results if r['BUY'] == 'YES']
        maybe_found = [r for r in results if r['BUY'] == 'MAYBE']
        if len(yes_found) >= 5 and len(maybe_found) >= 10: break
            
        status.text(f"🔍 Scanning {t} ({i}/{scan_limit}) | Found: {len(yes_found)} YES, {len(maybe_found)} MAYBE")
        
        try:
            df = yf.download(format_ticker(t), period="1y", interval="1d", progress=False)
            if df.empty or len(df) < 60: continue
            
            # --- Calculations ---
            price = float(df['Close'].iloc[-1])
            sma_50 = df['Close'].rolling(window=50).mean().iloc[-1]
            
            df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
            vwap_20 = (df['TP'] * df['Volume']).rolling(20).sum().iloc[-1] / df['Volume'].rolling(20).sum().iloc[-1]
            
            rsi = calculate_rsi(df['Close']).iloc[-1]
            avg_vol_60 = df['Volume'].rolling(window=60).mean().iloc[-1]
            rvol = df['Volume'].iloc[-1] / (avg_vol_60 + 1e-9)
            
            # ATR Exits
            tr = pd.concat([df['High']-df['Low'], (df['High']-df['Close'].shift()).abs(), (df['Low']-df['Close'].shift()).abs()], axis=1).max(axis=1)
            atr_14 = tr.rolling(window=14).mean().iloc[-1]

            # --- Scoring Logic ---
            c1 = (price > vwap_20 and price > sma_50) # Trend
            c2 = (45 <= rsi <= 60)                    # Momentum
            c3 = (rvol > 1.5)                         # Fuel
            
            conditions_met = sum([c1, c2, c3])
            
            is_buy = "NO"
            if conditions_met == 3:
                is_buy = "YES"
            elif conditions_met == 2:
                is_buy = "MAYBE"

            # Always keep DGNX, otherwise only keep YES/MAYBE
            if is_buy in ["YES", "MAYBE"] or t == 'DGNX':
                results.append({
                    'Ticker': t, 
                    'BUY': is_buy, 
                    'Price': round(price, 2),
                    'TP (3.5x)': round(price + (3.5 * atr_14), 2), 
                    'SL (1.5x)': round(price - (1.5 * atr_14), 2),
                    'RSI': round(rsi, 1), 
                    'RVOL': round(rvol, 2),
                    'Score': f"{conditions_met}/3"
                })
        except: continue
        p.progress(min((i + 1) / scan_limit, 1.0))

    status.empty(); p.empty()
    df = pd.DataFrame(results)
    
    if df.empty: return df
    
    # Sorting Logic
    df['SortOrder'] = df['BUY'].map({'YES': 0, 'MAYBE': 1, 'NO': 2})
    # Keep DGNX at absolute top
    df['IsDGNX'] = df['Ticker'].apply(lambda x: 0 if x == 'DGNX' else 1)
    
    df = df.sort_values(['IsDGNX', 'SortOrder', 'RVOL'], ascending=[True, True, False])
    return df.drop(columns=['SortOrder', 'IsDGNX'])

if st.button("🔍 EXECUTE TIERED SCAN"):
    data = get_tiered_swing_data()
    if not data.empty:
        def style_logic(row):
            if row['BUY'] == 'YES':
                return ['background-color: #2ecc71; color: white'] * len(row)
            if row['BUY'] == 'MAYBE':
                return ['background-color: #f39c12; color: white'] * len(row)
            return [''] * len(row)

        st.dataframe(data.style.apply(style_logic, axis=1), width='stretch', height=750)
    else:
        st.warning("No matches found in the current scan range.")