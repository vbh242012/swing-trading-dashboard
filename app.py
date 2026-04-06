import streamlit as st
import pandas as pd
import pandas_datareader.data as web
from finvizfinance.screener.overview import Overview
import numpy as np
import time
import warnings

# Quant-level configuration
warnings.filterwarnings("ignore")
st.set_page_config(page_title="Launchpad Pro: Stooq Edition", layout="wide")

# UI: CSS for Clean Table
st.markdown("""
    <style>
    .stDataFrame div[data-testid="stTable"] { overflow: visible !important; }
    .stDataFrame [data-testid="styled-data-frame"] { height: auto !important; }
    </style>
    """, unsafe_allow_html=True)

# UI: Header
st.title("🚀 7-14 Day Launchpad (Stooq Engine)")
st.info("""
**⚔️ 7-14 DAY SWING LAWS (STOOQ DATA)**
1. **TREND:** Price > 20D VWAP AND Price > 50D SMA.
2. **MOMENTUM:** RSI(14) between 45 and 60.
3. **FUEL:** RVOL > 1.5.
4. **EXIT:** 3.5x ATR Profit | 1.5x ATR Stop.
""")

def calculate_rsi(data, window=14):
    delta = data.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=window-1, adjust=False).mean()
    ema_down = down.ewm(com=window-1, adjust=False).mean()
    rs = ema_up / ema_down
    return 100 - (100 / (1 + rs))

@st.cache_data(ttl=3600)
def fetch_stooq_data():
    # 1. Pull Finviz Universe
    try:
        f = Overview()
        f.set_filter(filters_dict={'Price': '$2 to $10'})
        full_df = f.screener_view()
        all_tickers = full_df['Ticker'].tolist()
    except:
        all_tickers = ['PLUG', 'NIO', 'MARA', 'RIOT', 'F', 'AMD']

    # Force DGNX
    if 'DGNX' not in all_tickers: all_tickers.insert(0, 'DGNX')
    else:
        all_tickers.remove('DGNX'); all_tickers.insert(0, 'DGNX')

    found_setups = []
    dgnx_entry = None
    
    p_bar = st.progress(0)
    status = st.empty()
    
    # 2. Scanning Loop
    for i, ticker in enumerate(all_tickers):
        if len(found_setups) >= 5 and dgnx_entry is not None:
            break
        
        status.text(f"Scanning Stooq Tier... Found: {len(found_setups)}/5 | Ticker: {ticker}")
        
        try:
            # Stooq format requires .US suffix
            stooq_ticker = f"{ticker.replace('-', '.')}.US"
            
            # Fetch data (Daily)
            df = web.DataReader(stooq_ticker, 'stooq')
            
            # Stooq returns data in reverse chronological order; we need to sort it
            df = df.sort_index(ascending=True)
            
            if df.empty or len(df) < 60:
                continue

            # Standardizing Column Names (Stooq uses Title Case)
            df.columns = [c.capitalize() for c in df.columns]

            # --- Technical Engine ---
            price = float(df['Close'].iloc[-1])
            sma_50 = float(df['Close'].rolling(window=50).mean().iloc[-1])
            
            # 20D VWAP
            df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
            df['PV'] = df['TP'] * df['Volume']
            vwap_20 = float(df['PV'].rolling(window=20).sum().iloc[-1] / df['Volume'].rolling(window=20).sum().iloc[-1])
            
            # RVOL & RSI
            avg_vol_60 = float(df['Volume'].rolling(window=60).mean().iloc[-1])
            rvol = float(df['Volume'].iloc[-1] / avg_vol_60)
            rsi = float(calculate_rsi(df['Close']).iloc[-1])
            
            # ATR(14)
            tr = pd.concat([df['High'] - df['Low'], 
                            np.abs(df['High'] - df['Close'].shift()), 
                            np.abs(df['Low'] - df['Close'].shift())], axis=1).max(axis=1)
            atr_14 = float(tr.rolling(window=14).mean().iloc[-1])

            # --- Triple-Filter ---
            is_buy = "YES" if (price > vwap_20 and price > sma_50 and 45 <= rsi <= 60 and rvol > 1.5) else "NO"
            
            setup = {
                'Ticker': ticker, 'BUY (YES)': is_buy, 'Entry': round(price, 2),
                'Take Profit': round(price + (3.5 * atr_14), 2), 'Stop Loss': round(price - (1.5 * atr_14), 2),
                '20D VWAP': round(vwap_20, 2), '50D SMA': round(sma_50, 2), 'RSI': round(rsi, 1),
                'RVOL': round(rvol, 2), '60D Avg Vol': int(avg_vol_60)
            }

            if ticker == 'DGNX': dgnx_entry = setup
            if is_buy == "YES" and len(found_setups) < 5:
                found_setups.append(setup)
            
            # Micro-sleep to prevent Stooq throttling
            time.sleep(0.1)

        except Exception:
            continue
            
        p_bar.progress(min((i + 1) / len(all_tickers), 1.0))

    status.empty(); p_bar.empty()

    # Final Merge
    all_final = found_setups
    if dgnx_entry and not any(s['Ticker'] == 'DGNX' for s in all_final):
        all_final.append(dgnx_entry)
        
    return pd.DataFrame(all_final).sort_values(by=['BUY (YES)', 'RVOL'], ascending=[False, False])

if st.button("🔍 EXECUTE STOOQ SCAN", use_container_width=True):
    data = fetch_stooq_data()
    if not data.empty:
        st.dataframe(
            data.style.map(lambda x: 'color: #00FFFF; font-weight: bold;' if x == 'YES' else 'color: white;', subset=['BUY (YES)']),
            width='stretch', height=400
        )
    else:
        st.error("Data Source Connection Timeout. Please retry.")