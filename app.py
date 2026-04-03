import streamlit as st
import yfinance as yf
import pandas as pd
from finvizfinance.screener.overview import Overview
import warnings

warnings.filterwarnings("ignore")

st.set_page_config(page_title="Pro Swing Analyzer", layout="wide")

st.markdown("""
    <style>
    .stDataFrame div[data-testid="stTable"] { overflow: visible !important; }
    .stDataFrame [data-testid="styled-data-frame"] { height: auto !important; }
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR: THE LAWS ---
st.sidebar.title("⚔️ RUTHLESS SWING LAWS")
st.sidebar.markdown("""
**1. THE FLOOR:** Price **MUST** be > 20D VWAP.
**2. THE FUEL:** RVOL **MUST** be > 1.2.
**3. THE MOMENTUM:** RSI **MUST** be 45-60.
**4. THE WINDOW:** 7-14 Trading Days.
**5. THE EXIT:** 3.5x ATR Profit / 1.5x ATR Risk.
""")

st.title("📈 Pro Swing Analyzer ($3 - $10)")

def format_ticker(t):
    return t.replace('-', '.')

@st.cache_data(ttl=3600)
def get_swing_data():
    # 1. Get Universe ($3 - $10)
    try:
        f = Overview()
        f.set_filter(filters_dict={'Price': '$2 to $10'})
        full = f.screener_view()
        tickers = full[full['Price'] >= 3]['Ticker'].tolist()
    except:
        tickers = ['PLUG', 'NIO', 'MARA']

    # 2. FORCE DGNX (Bypass Price Filter)
    if 'DGNX' not in tickers:
        tickers.insert(0, 'DGNX')

    results = []
    yes_count = 0
    p = st.progress(0)
    status = st.empty()

    for i, t in enumerate(tickers):
        if i > 250: break # Higher limit for swing hunting
        if len(results) >= 25 and yes_count >= 5: break
            
        status.text(f"Scanning Ticker {i}: {t} | Found {yes_count}/5 BUY signals")
        y_ticker = format_ticker(t)
        try:
            s = yf.Ticker(y_ticker)
            h = s.history(period="6mo")
            if h.empty or len(h) < 25: continue
            
            price = h['Close'].iloc[-1]
            avg_vol = h['Volume'].tail(60).mean()
            rvol = h['Volume'].iloc[-1] / avg_vol
            
            # 20-Day Rolling VWAP (The Anchor)
            h['TP_Price'] = (h['High'] + h['Low'] + h['Close']) / 3
            h['PV'] = h['TP_Price'] * h['Volume']
            vwap_20 = h['PV'].tail(20).sum() / h['Volume'].tail(20).sum()
            
            tr = (h['High'] - h['Low']).rolling(14).mean().iloc[-1]
            
            delta = h['Close'].diff()
            rsi = 100 - (100 / (1 + (delta.clip(lower=0).rolling(14).mean() / -delta.clip(upper=0).rolling(14).mean()).iloc[-1]))

            # SWING BUY LOGIC
            is_buy = "YES" if (price > vwap_20 and 45 < rsi < 60 and rvol > 1.2) else "NO"
            if is_buy == "YES": yes_count += 1

            results.append({
                'Ticker': t, 'BUY': is_buy, 'Price': round(price, 2),
                'TP': round(price + (3.5 * tr), 2), 'SL': round(price - (1.5 * tr), 2),
                '20D VWAP': round(vwap_20, 2), 'RSI': round(rsi, 1), 'RVOL': round(rvol, 2), '60D Avg Vol': int(avg_vol)
            })
        except: continue
        p.progress(min((i + 1) / 250, 1.0))
        
    df = pd.DataFrame(results).sort_values(['BUY', '60D Avg Vol'], ascending=[False, False])
    status.empty()
    p.empty()
    return df.head(25)

if st.button("🚀 EXECUTE RUTHLESS SWING SCAN"):
    data = get_swing_data()
    st.dataframe(
        data.style.map(lambda x: 'background-color: #3498db; color: white;' if x == 'YES' else '', subset=['BUY']),
        width='stretch', height=1000
    )