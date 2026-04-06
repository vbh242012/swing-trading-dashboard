import streamlit as st
import yfinance as yf
import pandas as pd
from finvizfinance.screener.overview import Overview
import numpy as np
import warnings

# Quant-level configuration
warnings.filterwarnings("ignore")
st.set_page_config(page_title="7-14 Day Swing Launchpad", layout="wide")

# UI: CSS for Clean Table & Visual Priority
st.markdown("""
    <style>
    .stDataFrame div[data-testid="stTable"] { overflow: visible !important; }
    .stDataFrame [data-testid="styled-data-frame"] { height: auto !important; }
    th { background-color: #1E1E1E !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# UI: Header Reminders
st.title("🚀 7-14 Day Swing Launchpad")
st.info("""
**⚔️ 7-14 DAY SWING LAWS**
1. **THE TREND:** Price > 20D Rolling VWAP (Institutional Floor) AND Price > 50D SMA (Primary Trend).
2. **THE MOMENTUM:** RSI(14) between 45 and 60 (The "Sweet Spot" before the spike).
3. **THE FUEL:** RVOL > 1.5 (Evidence of big-money accumulation).
4. **THE EXIT:** 3.5x ATR Profit Target | 1.5x ATR Safety Stop.
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
    # 1. Pipeline: Pull Universe
    try:
        f = Overview()
        f.set_filter(filters_dict={'Price': '$2 to $10'})
        full_df = f.screener_view()
        all_tickers = full_df['Ticker'].tolist()
    except Exception:
        # Fallback list if Finviz API is throttled
        all_tickers = ['PLUG', 'NIO', 'MARA', 'RIOT', 'F', 'AMD', 'PFE', 'AAL', 'LCID', 'GRAB']

    # 2. DGNX Exception: Ensure it's in the queue
    if 'DGNX' not in all_tickers:
        all_tickers.insert(0, 'DGNX')
    else:
        all_tickers.remove('DGNX')
        all_tickers.insert(0, 'DGNX')

    found_setups = []
    dgnx_data = None
    
    p_bar = st.progress(0)
    status = st.empty()
    
    # 3. Core Algorithm: The Hunt for 5
    for i, ticker in enumerate(all_tickers):
        if len(found_setups) >= 5 and dgnx_data is not None:
            break
        
        status.text(f"Scanning Ticker {i}/{len(all_tickers)}: {ticker} | Found: {len(found_setups)}/5")
        y_ticker = sanitize_ticker(ticker)
        
        try:
            # Fetch 1 year for SMA and VWAP accuracy
            df = yf.download(y_ticker, period="1y", interval="1d", progress=False)
            if df.empty or len(df) < 60:
                continue

            # --- Technical Engine ---
            price = df['Close'].iloc[-1]
            
            # 50-Day SMA
            sma_50 = df['Close'].rolling(window=50).mean().iloc[-1]
            
            # 20-Day Rolling VWAP
            # Formula: Sum(P * V) / Sum(V)
            df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
            df['PV'] = df['TP'] * df['Volume']
            vwap_20 = df['PV'].rolling(window=20).sum().iloc[-1] / df['Volume'].rolling(window=20).sum().iloc[-1]
            
            # RVOL (Current Vol / 60D Avg Vol)
            avg_vol_60 = df['Volume'].rolling(window=60).mean().iloc[-1]
            rvol = df['Volume'].iloc[-1] / avg_vol_60
            
            # RSI(14)
            rsi = calculate_rsi(df['Close']).iloc[-1]
            
            # ATR(14) for Exits
            high_low = df['High'] - df['Low']
            high_cp = np.abs(df['High'] - df['Close'].shift())
            low_cp = np.abs(df['Low'] - df['Close'].shift())
            tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
            atr_14 = tr.rolling(window=14).mean().iloc[-1]

            # --- Logic Filters ---
            trend_pass = (price > vwap_20) and (price > sma_50)
            momentum_pass = (45 <= rsi <= 60)
            fuel_pass = (rvol > 1.5)
            
            is_buy = "YES" if (trend_pass and momentum_pass and fuel_pass) else "NO"
            
            entry_price = round(float(price), 2)
            setup = {
                'Ticker': ticker,
                'BUY (YES)': is_buy,
                'Entry': entry_price,
                'Take Profit': round(entry_price + (3.5 * atr_14), 2),
                'Stop Loss': round(entry_price - (1.5 * atr_14), 2),
                '20D VWAP': round(float(vwap_20), 2),
                '50D SMA': round(float(sma_50), 2),
                'RSI': round(float(rsi), 1),
                'RVOL': round(float(rvol), 2),
                '60D Avg Vol': int(avg_vol_60)
            }

            # Capture DGNX specifically
            if ticker == 'DGNX':
                dgnx_data = setup
            
            # Add to setups if it's a Launchpad
            if is_buy == "YES" and len(found_setups) < 5:
                found_setups.append(setup)

        except Exception:
            continue
            
        p_bar.progress(min((i + 1) / 500, 1.0))

    p_bar.empty()
    status.empty()

    # 4. Final Compilation
    # Combine DGNX and the found setups, sort by RVOL
    final_list = found_setups
    if dgnx_data and not any(s['Ticker'] == 'DGNX' for s in final_list):
        final_list.append(dgnx_data)
        
    res_df = pd.DataFrame(final_list)
    if not res_df.empty:
        # Prioritize "YES" signals, then sort by highest RVOL
        res_df = res_df.sort_values(by=['BUY (YES)', 'RVOL'], ascending=[False, False]).head(6) 
    return res_df

# UI Execution
if st.button("🔍 SCAN FOR 7-14 DAY SETUPS", width='stretch'):
    data = fetch_launchpad_data()
    
    if not data.empty:
        # Style logic for Electric Blue Highlighting
        def color_buy_column(val):
            color = '#00FFFF' if val == 'YES' else 'white' # Cyan/Electric Blue
            return f'color: {color}; font-weight: bold;'

        st.dataframe(
            data.style.map(color_buy_column, subset=['BUY (YES)']),
            width='stretch',
            height=400
        )
    else:
        st.warning("The market is currently too volatile or too quiet. No stocks met the Triple-Filter Launchpad criteria.")