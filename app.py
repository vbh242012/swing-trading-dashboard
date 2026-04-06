import streamlit as st
import yfinance as yf
import pandas as pd
from finvizfinance.screener.overview import Overview
import numpy as np
import warnings

warnings.filterwarnings("ignore")

st.set_page_config(page_title="7-14 Day Swing Launchpad", layout="wide")

# CSS to ensure table expands fully without internal scrollbars
st.markdown("""
    <style>
    .stDataFrame div[data-testid="stTable"] { overflow: visible !important; }
    .stDataFrame [data-testid="styled-data-frame"] { height: auto !important; }
    </style>
    """, unsafe_allow_html=True)

# --- HEADER RULES ---
st.title("🚀 7-14 Day Swing Launchpad")

st.info("""
**⚔️ 7-14 DAY SWING LAWS**
1. **THE TREND:** Price > 20D Rolling VWAP AND 50D SMA.
2. **THE MOMENTUM:** RSI(14) must be between 45-60 (The Launchpad).
3. **THE FUEL:** RVOL must be > 1.5 (Institutional Entry).
4. **THE EXIT:** 3.5x ATR Profit Target / 1.5x ATR Safety Stop.
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
    # 1. Get Universe ($2 to $10 range for optimal swing volatility)
    try:
        f = Overview()
        f.set_filter(filters_dict={'Price': '$2 to $10'})
        tickers = f.screener_view()['Ticker'].tolist()
    except:
        tickers = ['DGNX', 'PLUG', 'NIO', 'F', 'AAL']
    
    # 2. FORCE DGNX Priority
    if 'DGNX' not in tickers:
        tickers.insert(0, 'DGNX')
    else:
        tickers.remove('DGNX')
        tickers.insert(0, 'DGNX')

    results = []
    yes_count = 0
    p = st.progress(0)
    status = st.empty()

    # 3. Process until we find exactly 5 "YES" signals (plus others up to 25 total)
    for i, t in enumerate(tickers):
        if i > 300: break # Safety cap for API limits
        if yes_count >= 5 and len(results) >= 10: break
            
        status.text(f"Scanning Ticker {i}: {t} | Found {yes_count}/5 Launchpad signals")
        y_ticker = format_ticker(t)
        
        try:
            # Fetch 1 year of daily data for SMA and VWAP accuracy
            df = yf.download(y_ticker, period="1y", interval="1d", progress=False)
            if df.empty or len(df) < 60: continue
            
            # --- Technical Calculations ---
            price = float(df['Close'].iloc[-1])
            
            # 50D SMA
            sma_50 = df['Close'].rolling(window=50).mean().iloc[-1]
            
            # 20D Rolling VWAP
            df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
            df['PV'] = df['TP'] * df['Volume']
            vwap_20 = df['PV'].rolling(window=20).sum().iloc[-1] / df['Volume'].rolling(window=20).sum().iloc[-1]
            
            # RSI(14)
            rsi = calculate_rsi(df['Close']).iloc[-1]
            
            # RVOL (Current Vol vs 60D Avg)
            avg_vol_60 = df['Volume'].rolling(window=60).mean().iloc[-1]
            rvol = df['Volume'].iloc[-1] / avg_vol_60
            
            # Swing-Wide ATR(14)
            high_low = df['High'] - df['Low']
            high_cp = np.abs(df['High'] - df['Close'].shift())
            low_cp = np.abs(df['Low'] - df['Close'].shift())
            tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
            atr_14 = tr.rolling(window=14).mean().iloc[-1]

            # --- The 7-14 Day Launchpad Logic ---
            trend_pass = (price > vwap_20) and (price > sma_50)
            momentum_pass = (45 <= rsi <= 60)
            fuel_pass = (rvol > 1.5)
            
            is_buy = "YES" if (trend_pass and momentum_pass and fuel_pass) else "NO"
            
            # DGNX Exception: Force into results even if NO
            if is_buy == "YES" or t == 'DGNX':
                if is_buy == "YES": yes_count += 1
                
                results.append({
                    'Ticker': t, 
                    'BUY': is_buy, 
                    'Entry': round(price, 2),
                    'Take Profit (3.5x)': round(price + (3.5 * atr_14), 2), 
                    'Stop Loss (1.5x)': round(price - (1.5 * atr_14), 2),
                    'RSI': round(rsi, 1), 
                    'RVOL': round(rvol, 2), 
                    '20D VWAP': round(vwap_20, 2),
                    '50D SMA': round(sma_50, 2),
                    '60D Avg Vol': int(avg_vol_60)
                })
        except: continue
        p.progress(min((i + 1) / 300, 1.0))

    # Sort results to put BUY signals at top, followed by DGNX
    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values(['BUY', 'RVOL'], ascending=[False, False])
        
    status.empty()
    p.empty()
    return df

if st.button("🔍 EXECUTE SWING SCAN"):
    data = get_swing_data()
    if not data.empty:
        st.dataframe(
            data.style.map(lambda x: 'background-color: #2ecc71; color: white;' if x == 'YES' else '', subset=['BUY']),
            width='stretch', height=600
        )
    else:
        st.warning("No matches found. Market conditions may be too restrictive.")