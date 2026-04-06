import streamlit as st
import yfinance as yf
import pandas as pd
from finvizfinance.screener.overview import Overview
import warnings

warnings.filterwarnings("ignore")

st.set_page_config(page_title="High-Prob Swing Pro", layout="wide")

# Sidebar Laws
st.sidebar.title("⚔️ RUTHLESS SWING LAWS")
st.sidebar.markdown("""
**1. TRIPLE THREAT:** Price > 20D VWAP > 50D SMA.
**2. MOMENTUM:** RSI strictly 45-60.
**3. LIQUIDITY:** RVOL > 1.5.
**4. DGNX:** Always included.
""")

st.title("📈 High-Probability Swing Analyzer ($3 - $10)")

def format_ticker(t):
    return t.replace('-', '.')

@st.cache_data(ttl=3600)
def get_swing_data():
    try:
        f = Overview()
        f.set_filter(filters_dict={'Price': '$2 to $20'}) # Wide pull
        full = f.screener_view()
        tickers = full['Ticker'].tolist()
    except:
        tickers = ['MARA', 'RIOT', 'PLUG', 'NIO', 'F', 'AMD']

    # Force DGNX to the front
    if 'DGNX' not in tickers: tickers.insert(0, 'DGNX')
    else:
        tickers.remove('DGNX'); tickers.insert(0, 'DGNX')

    results = []
    yes_count = 0
    p = st.progress(0)
    status = st.empty()

    for i, t in enumerate(tickers):
        if i > 500: break # Deep scan to find the best 5 YES
        if len(results) >= 40 and yes_count >= 5: break
            
        status.text(f"Scanning {i}/{len(tickers)}: {t} | High-Prob Signals: {yes_count}/5")
        y_ticker = format_ticker(t)
        
        try:
            s = yf.Ticker(y_ticker)
            h = s.history(period="1y") # 1 year for 50SMA
            if h.empty or len(h) < 50: continue
            
            price = h['Close'].iloc[-1]
            
            # STRICT Price Filter (3-10) for everyone but DGNX
            if t != 'DGNX' and not (3.0 <= price <= 10.0): continue

            # Calculations
            h['50SMA'] = h['Close'].rolling(50).mean()
            h['TP_Price'] = (h['High'] + h['Low'] + h['Close']) / 3
            h['PV'] = h['TP_Price'] * h['Volume']
            vwap_20 = h['PV'].tail(20).sum() / h['Volume'].tail(20).sum()
            avg_vol = h['Volume'].tail(60).mean()
            rvol = h['Volume'].iloc[-1] / avg_vol
            tr = (h['High'] - h['Low']).rolling(14).mean().iloc[-1]
            
            delta = h['Close'].diff()
            rsi = 100 - (100 / (1 + (delta.clip(lower=0).rolling(14).mean() / -delta.clip(upper=0).rolling(14).mean()).iloc[-1]))

            # TIGHTENED RULES
            sma_50 = h['50SMA'].iloc[-1]
            is_buy = "YES" if (price > vwap_20 and price > sma_50 and 45 < rsi < 60 and rvol > 1.5) else "NO"
            
            if is_buy == "YES": yes_count += 1

            results.append({
                'Ticker': t, 'BUY': is_buy, 'Price': round(price, 2),
                'TP': round(price + (3.5 * tr), 2), 'SL': round(price - (1.5 * tr), 2),
                '20D VWAP': round(vwap_20, 2), '50D SMA': round(sma_50, 2),
                'RSI': round(rsi, 1), 'RVOL': round(rvol, 2), '60D Avg Vol': int(avg_vol)
            })
        except: continue
        p.progress(min((i + 1) / 500, 1.0))
        
    df_pool = pd.DataFrame(results)
    yes_df = df_pool[df_pool['BUY'] == "YES"]
    dgnx_df = df_pool[df_pool['Ticker'] == 'DGNX']
    no_df = df_pool[df_pool['BUY'] == "NO"]
    
    final_df = pd.concat([yes_df, dgnx_df, no_df]).drop_duplicates(subset=['Ticker']).head(25)
    status.empty(); p.empty()
    return final_df.sort_values('60D Avg Vol', ascending=False)

if st.button("🚀 EXECUTE RUTHLESS SWING SCAN"):
    data = get_swing_data()
    st.dataframe(data.style.map(lambda x: 'background-color: #3498db; color: white;' if x == 'YES' else '', subset=['BUY']), width='stretch', height=1000)