import streamlit as st
import yfinance as yf
import pandas as pd
from finvizfinance.screener.overview import Overview
import warnings

warnings.filterwarnings("ignore")

st.set_page_config(page_title="Swing Pro ($3-$10)", layout="wide")

st.markdown("""
    <style>
    .stDataFrame div[data-testid="stTable"] { overflow: visible !important; }
    .stDataFrame [data-testid="styled-data-frame"] { height: auto !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("📈 Pro Swing Analyzer ($3 - $10)")
st.sidebar.info("""
**⚔️ RUTHLESS LAWS (SWING)**
1. **FLOOR**: Price > 20-Day VWAP.
2. **FUEL**: RVOL > 1.2.
3. **MOMENTUM**: RSI 45-60.
4. **WINDOW**: 7-14 Days.
""")

@st.cache_data(ttl=3600)
def get_swing_data():
    try:
        f = Overview()
        f.set_filter(filters_dict={'Price': '$2 to $10'})
        full_universe = f.screener_view()
        # Filter for the exact $3-$10 range
        tickers = full_universe[(full_universe['Price'] >= 3)]['Ticker'].tolist()
    except:
        tickers = ['PLUG', 'NIO', 'MARA', 'RIOT', 'F', 'PFE']

    if 'DGNX' not in tickers:
        tickers.append('DGNX')

    results = []
    p = st.progress(0)
    status = st.empty()
    
    total = len(tickers)
    for i, t in enumerate(tickers):
        status.text(f"Scanning {i}/{total}: {t}")
        try:
            s = yf.Ticker(t)
            h = s.history(period="6mo") # Daily candles for swing
            if len(h) < 50: continue
            
            price = h['Close'].iloc[-1]
            avg_vol = h['Volume'].tail(60).mean()
            rvol = h['Volume'].iloc[-1] / avg_vol
            
            # Swing VWAP (Average of last 20 days)
            vwap = (h['Close'] * h['Volume']).tail(20).sum() / h['Volume'].tail(20).sum()
            
            # Daily ATR for wider swing targets
            tr = (h['High'] - h['Low']).rolling(14).mean().iloc[-1]
            
            # RSI 14
            delta = h['Close'].diff()
            up = delta.clip(lower=0).rolling(14).mean()
            down = -delta.clip(upper=0).rolling(14).mean()
            rsi = 100 - (100 / (1 + (up / down).iloc[-1]))

            # RUTHLESS SWING CONDITION
            is_buy = "YES" if (price > vwap and 45 < rsi < 60 and rvol > 1.2) else "NO"

            results.append({
                'Ticker': t, 'BUY': is_buy, 'Entry Price': round(price, 2),
                'Take Profit': round(price + (3.5 * tr), 2), 'Stop Loss': round(price - (1.5 * tr), 2),
                'RSI': round(rsi, 1), 'RVOL': round(rvol, 2), '60D Avg Vol': int(avg_vol)
            })
        except: continue
        p.progress((i + 1) / total)
        
    df_results = pd.DataFrame(results)
    
    # Sort by Volume and pick Top 25
    top_25 = df_results.sort_values('60D Avg Vol', ascending=False).head(25)
    
    # Ensure DGNX is present
    if 'DGNX' not in top_25['Ticker'].values and 'DGNX' in df_results['Ticker'].values:
        dgnx_row = df_results[df_results['Ticker'] == 'DGNX']
        top_25 = pd.concat([top_25, dgnx_row])

    status.empty()
    p.empty()
    return top_25

if st.button("🚀 EXECUTE FULL SWING SCAN"):
    data = get_swing_data()
    st.dataframe(
        data.style.map(lambda x: 'background-color: #3498db; color: white;' if x == 'YES' else '', subset=['BUY']),
        use_container_width=True,
        height=1000
    )