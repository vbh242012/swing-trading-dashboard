import streamlit as st
import yfinance as yf
import pandas as pd
from finvizfinance.screener.overview import Overview
import numpy as np
import warnings

warnings.filterwarnings("ignore")

st.set_page_config(page_title="Swing Pro ($3-$10)", layout="wide")
st.markdown("<style>.stDataFrame div[data-testid='stTable'] {overflow: visible !important;} .stDataFrame [data-testid='styled-data-frame'] {height: auto !important;}</style>", unsafe_allow_html=True)

st.title("📈 Pro Swing Analyzer ($3 - $10)")

@st.cache_data(ttl=3600)
def get_swing_data():
    try:
        f = Overview()
        f.set_filter(filters_dict={'Price': '$2 to $10'})
        full = f.screener_view()
        tickers = full[full['Price'] >= 3]['Ticker'].tolist()
    except: tickers = ['PLUG', 'NIO', 'MARA', 'DGNX']

    if 'DGNX' not in tickers: tickers.append('DGNX')

    results = []
    p = st.progress(0)
    total = len(tickers)
    
    for i, t in enumerate(tickers):
        try:
            s = yf.Ticker(t)
            h = s.history(period="6mo")
            if len(h) < 20: continue
            
            price = h['Close'].iloc[-1]
            avg_vol = h['Volume'].tail(60).mean()
            rvol = h['Volume'].iloc[-1] / avg_vol
            
            # CALCULATING 20-DAY ROLLING VWAP
            # (Typical Price * Volume) / Volume over last 20 days
            h['TP'] = (h['High'] + h['Low'] + h['Close']) / 3
            h['PV'] = h['TP'] * h['Volume']
            vwap_20 = h['PV'].tail(20).sum() / h['Volume'].tail(20).sum()
            
            tr = (h['High'] - h['Low']).rolling(14).mean().iloc[-1]
            
            # RSI
            delta = h['Close'].diff()
            up = delta.clip(lower=0).rolling(14).mean()
            down = -delta.clip(upper=0).rolling(14).mean()
            rsi = 100 - (100 / (1 + (up / down).iloc[-1]))

            is_buy = "YES" if (price > vwap_20 and 45 < rsi < 60 and rvol > 1.2) else "NO"

            results.append({
                'Ticker': t, 'BUY': is_buy, 'Entry Price': round(price, 2),
                'Take Profit': round(price + (3.5 * tr), 2), 'Stop Loss': round(price - (1.5 * tr), 2),
                '20-Day VWAP': round(vwap_20, 2), 'RSI': round(rsi, 1), 'RVOL': round(rvol, 2), '60D Avg Vol': int(avg_vol)
            })
        except: continue
        p.progress((i + 1) / total)
        
    df = pd.DataFrame(results).sort_values('60D Avg Vol', ascending=False).head(25)
    if 'DGNX' not in df['Ticker'].values and any(r['Ticker'] == 'DGNX' for r in results):
        df = pd.concat([df, pd.DataFrame([next(r for r in results if r['Ticker'] == 'DGNX')])])
        
    p.empty()
    return df

if st.button("🚀 EXECUTE SWING SCAN"):
    data = get_swing_data()
    st.dataframe(data.style.map(lambda x: 'background-color: #3498db; color: white;' if x == 'YES' else '', subset=['BUY']), use_container_width=True, height=1000)