import streamlit as st
import yfinance as yf
import pandas as pd
from finvizfinance.screener.overview import Overview
import warnings

warnings.filterwarnings("ignore")

st.set_page_config(page_title="Swing Pro ($3-$10)", layout="wide")
st.markdown("<style>.stDataFrame div[data-testid='stTable'] {overflow: visible !important;} .stDataFrame [data-testid='styled-data-frame'] {height: auto !important;}</style>", unsafe_allow_html=True)

st.title("📈 Pro Swing Analyzer ($3 - $10)")

def format_ticker(t):
    return t.replace('-', '.')

@st.cache_data(ttl=3600)
def get_swing_data():
    try:
        f = Overview()
        f.set_filter(filters_dict={'Price': '$2 to $10'})
        full = f.screener_view()
        tickers = full[full['Price'] >= 3]['Ticker'].tolist()
    except: 
        tickers = ['PLUG', 'NIO', 'MARA', 'DGNX']

    if 'DGNX' not in tickers: tickers.insert(0, 'DGNX')

    results = []
    p = st.progress(0)
    status = st.empty()
    
    yes_count = 0
    for i, t in enumerate(tickers):
        if i > 150: break # Scan limit
        if len(results) >= 25 and yes_count >= 5 and 'DGNX' in [r['Ticker'] for r in results]:
            break
            
        status.text(f"Hunting for Swing Buys... Found {yes_count}/5. Scanning: {t}")
        y_ticker = format_ticker(t)
        try:
            s = yf.Ticker(y_ticker)
            h = s.history(period="6mo")
            if h.empty or len(h) < 20: continue
            
            price = h['Close'].iloc[-1]
            avg_vol = h['Volume'].tail(60).mean()
            rvol = h['Volume'].iloc[-1] / avg_vol
            
            # 20-Day Rolling VWAP
            h['TP'] = (h['High'] + h['Low'] + h['Close']) / 3
            h['PV'] = h['TP'] * h['Volume']
            vwap_20 = h['PV'].tail(20).sum() / h['Volume'].tail(20).sum()
            tr = (h['High'] - h['Low']).rolling(14).mean().iloc[-1]
            
            # RSI 14
            delta = h['Close'].diff()
            rsi = 100 - (100 / (1 + (delta.clip(lower=0).rolling(14).mean() / -delta.clip(upper=0).rolling(14).mean()).iloc[-1]))

            is_buy = "YES" if (price > vwap_20 and 45 < rsi < 60 and rvol > 1.2) else "NO"
            if is_buy == "YES": yes_count += 1

            results.append({
                'Ticker': t, 'BUY': is_buy, 'Entry Price': round(price, 2),
                'Take Profit': round(price + (3.5 * tr), 2), 'Stop Loss': round(price - (1.5 * tr), 2),
                '20-Day VWAP': round(vwap_20, 2), 'RSI': round(rsi, 1), 'RVOL': round(rvol, 2), '60D Avg Vol': int(avg_vol)
            })
        except: continue
        p.progress(min((i + 1) / 150, 1.0))
        
    df_all = pd.DataFrame(results)
    
    # Filter and prioritize YES signals
    yes_df = df_all[df_all['BUY'] == "YES"]
    no_df = df_all[df_all['BUY'] == "NO"]
    dgnx_row = df_all[df_all['Ticker'] == 'DGNX']
    
    combined = pd.concat([yes_df, no_df, dgnx_row]).drop_duplicates(subset=['Ticker'])
    final_df = combined.sort_values(['BUY', '60D Avg Vol'], ascending=[False, False]).head(25)
    
    # Sort for final volume-based display
    final_df = final_df.sort_values('60D Avg Vol', ascending=False)
        
    status.empty()
    p.empty()
    return final_df

if st.button("🚀 EXECUTE RUTHLESS SWING SCAN"):
    data = get_swing_data()
    st.dataframe(
        data.style.map(lambda x: 'background-color: #3498db; color: white;' if x == 'YES' else '', subset=['BUY']), 
        width='stretch', height=1000
    )