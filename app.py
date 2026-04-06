import streamlit as st
import yfinance as yf
import pandas as pd
from finvizfinance.screener.overview import Overview
import numpy as np
import warnings

warnings.filterwarnings("ignore")

st.set_page_config(page_title="7-14 Day Swing Launchpad", layout="wide")

# CSS to ensure table expands fully
st.markdown("""
    <style>
    .stDataFrame div[data-testid="stTable"] { overflow: visible !important; }
    .stDataFrame [data-testid="styled-data-frame"] { height: auto !important; }
    </style>
    """, unsafe_allow_html=True)

# --- HEADER RULES ---
st.title("🚀 7-14 Day Swing Launchpad (Tiered)")

st.info("""
**⚔️ 7-14 DAY SWING LAWS**
1. **YES:** Price > VWAP/SMA **AND** RSI 45-60 **AND** RVOL > 1.5.
2. **MAYBE:** 2 Rules Pass **AND** 3rd Rule is > 60% of target.
3. **EXIT:** 3.5x ATR Profit Target / 1.5x ATR Safety Stop.
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
def get_swing_data():
    try:
        f = Overview()
        f.set_filter(filters_dict={'Price': '$2 to $10'})
        tickers = f.screener_view()['Ticker'].tolist()
    except:
        tickers = ['DGNX', 'PLUG', 'NIO', 'F', 'AAL']
    
    if 'DGNX' not in tickers: tickers.insert(0, 'DGNX')
    else:
        tickers.remove('DGNX'); tickers.insert(0, 'DGNX')

    results = []
    yes_count = 0
    p = st.progress(0)
    status = st.empty()

    # Process a larger batch to fill the 10 'MAYBE' slots
    scan_limit = 250 
    for i, t in enumerate(tickers[:scan_limit]):
        # Break only if we have our 5 YES and 10 MAYBE (or hit limit)
        yes_found = [r for r in results if r['BUY'] == 'YES']
        maybe_found = [r for r in results if r['BUY'] == 'MAYBE']
        if len(yes_found) >= 5 and len(maybe_found) >= 10: break
            
        status.text(f"Scanning {t} ({i}/{scan_limit}) | Found: {len(yes_found)} YES, {len(maybe_found)} MAYBE")
        
        try:
            df = yf.download(format_ticker(t), period="1y", interval="1d", progress=False)
            if df.empty or len(df) < 60: continue
            
            # --- Data Points ---
            price = float(df['Close'].iloc[-1])
            sma_50 = df['Close'].rolling(window=50).mean().iloc[-1]
            df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
            vwap_20 = df['TP'].rolling(window=20).sum().iloc[-1] / (df['Volume'].rolling(window=20).sum().iloc[-1] / df['Volume'].rolling(window=20).mean().iloc[-1] * 20) # Simplified proxy for daily roll
            # Re-calculating actual VWAP logic for better accuracy
            vwap_20 = (df['TP'] * df['Volume']).rolling(20).sum().iloc[-1] / df['Volume'].rolling(20).sum().iloc[-1]
            
            rsi = calculate_rsi(df['Close']).iloc[-1]
            avg_vol_60 = df['Volume'].rolling(window=60).mean().iloc[-1]
            rvol = df['Volume'].iloc[-1] / avg_vol_60
            
            # ATR
            tr = pd.concat([df['High']-df['Low'], (df['High']-df['Close'].shift()).abs(), (df['Low']-df['Close'].shift()).abs()], axis=1).max(axis=1)
            atr_14 = tr.rolling(window=14).mean().iloc[-1]

            # --- TIERED LOGIC ---
            # Define passing conditions
            c1 = (price > vwap_20 and price > sma_50)
            c2 = (45 <= rsi <= 60)
            c3 = (rvol > 1.5)
            
            # Define "Near Miss" (60% of target)
            m1 = (price > vwap_20 * 0.98) # Price within 2% of trend
            m2 = (40 <= rsi <= 65)        # RSI slightly wider
            m3 = (rvol > 0.9)             # 60% of the 1.5 RVOL target
            
            conditions = [c1, c2, c3]
            near_misses = [m1, m2, m3]
            
            score = sum(conditions)
            is_buy = "NO"
            
            if score == 3:
                is_buy = "YES"
                yes_count += 1
            elif score == 2:
                # Check if the 3rd failed condition meets the 60% threshold
                failed_idx = conditions.index(False)
                if near_misses[failed_idx]:
                    is_buy = "MAYBE"

            if is_buy in ["YES", "MAYBE"] or t == 'DGNX':
                results.append({
                    'Ticker': t, 'BUY': is_buy, 'Entry': round(price, 2),
                    'TP (3.5x)': round(price + (3.5 * atr_14), 2), 
                    'SL (1.5x)': round(price - (1.5 * atr_14), 2),
                    'RSI': round(rsi, 1), 'RVOL': round(rvol, 2), 
                    '20D VWAP': round(vwap_20, 2), '50D SMA': round(sma_50, 2)
                })
        except: continue
        p.progress(min((i + 1) / scan_limit, 1.0))

    df = pd.DataFrame(results)
    status.empty(); p.empty()
    
    if df.empty: return df
    
    # Sort: DGNX first, then YES by RVOL, then MAYBE by RVOL
    df['Sort'] = df['BUY'].map({'YES': 1, 'MAYBE': 2, 'NO': 3})
    dgnx = df[df['Ticker'] == 'DGNX']
    others = df[df['Ticker'] != 'DGNX'].sort_values(['Sort', 'RVOL'], ascending=[True, False])
    
    return pd.concat([dgnx, others]).drop(columns=['Sort'])

if st.button("🔍 EXECUTE TIERED SCAN"):
    data = get_swing_data()
    if not data.empty:
        def style_rows(row):
            if row['BUY'] == 'YES': return ['background-color: #2ecc71; color: white'] * len(row)
            if row['BUY'] == 'MAYBE': return ['background-color: #f39c12; color: white'] * len(row)
            return [''] * len(row)

        st.dataframe(data.style.apply(style_rows, axis=1), width='stretch', height=800)
    else:
        st.warning("No matches found.")