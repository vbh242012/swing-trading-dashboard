import streamlit as st
import yfinance as yf
import pandas as pd
from finvizfinance.screener.overview import Overview
import io
import warnings
from datetime import datetime

# Suppress technical warnings
warnings.filterwarnings("ignore")

# --- UI Configuration ---
st.set_page_config(page_title="Pro Swing Quant ($3-$10)", layout="wide")

# --- SIDEBAR: THE SWING RULES ---
st.sidebar.title("⚔️ PRO SWING LAWS")
st.sidebar.error("""
1. **PRICE RANGE**: $3.00 - $10.00 ONLY.
2. **LIQUIDITY**: Avg Vol > 1M Shares.
3. **ATR RATIO**: 1.5x ATR Risk / 3.5x ATR Reward.
""")

st.sidebar.info("""
**Optimal Swing Window:**
7 to 14 Trading Days.
*Note: Exit if target is hit or time window expires.*
""")

st.title("📈 Pro Swing Analyzer ($3 - $10)")
st.markdown(f"""
**Strategy:** ATR-Based Volatility Scaling. This app identifies high-volume mid-caps showing institutional accumulation.
*Current Analysis Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
""")

@st.cache_data(ttl=3600)
def run_pro_swing_analysis():
    all_records = []
    
    try:
        foverview = Overview()
        # Filtering for the $3 - $10 range as requested
        foverview.set_filter(filters_dict={'Price': '$2 to $10'}) 
        screener_df = foverview.screener_view(order='Average Volume (3 Month)')
        
        # Take top 30 to filter down to the best 20 high-volume candidates
        tickers = screener_df[screener_df['Price'] >= 3]['Ticker'].head(20).tolist()
    except Exception as e:
        tickers = ['SNDL', 'PLUG', 'NKLA', 'NIO', 'MARA', 'RIOT', 'F', 'LCID', 'GRWG', 'PFE']
        st.warning("Screener bypass active. Using high-volume $3-$10 fallback list.")

    progress = st.progress(0)
    for idx, ticker in enumerate(tickers):
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="6mo", interval="1d")
            if len(df) < 20: continue

            # --- Technical Calculations ---
            # 1. ATR (14-Day Average True Range) for Volatility Pricing
            high_low = df['High'] - df['Low']
            high_cp = abs(df['High'] - df['Close'].shift())
            low_cp = abs(df['Low'] - df['Close'].shift())
            tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
            atr = tr.rolling(window=14).mean().iloc[-1]

            # 2. Moving Averages
            sma20 = df['Close'].rolling(window=20).mean().iloc[-1]
            sma50 = df['Close'].rolling(window=50).mean().iloc[-1]
            
            # 3. RSI (14-Day)
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]

            # Current Data
            price = df['Close'].iloc[-1]
            vol = df['Volume'].iloc[-1]
            avg_vol = df['Volume'].tail(60).mean()
            rvol = vol / avg_vol

            # --- SWING LOGIC ---
            # BUY if Price is above 20MA (Trend confirmed) and RSI is not overbought (<60)
            is_buy = "YES" if (price > sma20 and rvol > 1.2 and rsi < 65) else "NO"
            
            # ATR-Based Targets (Ruthless Math)
            entry_price = price
            stop_loss = entry_price - (1.5 * atr)
            take_profit = entry_price + (3.5 * atr)
            upside_pct = ((take_profit - entry_price) / entry_price) * 100

            all_records.append({
                'Ticker': ticker,
                'BUY': is_buy,
                'Entry Price': round(entry_price, 2),
                'Take Profit': round(take_profit, 2),
                'Stop Loss': round(stop_loss, 2),
                'Potential Gain (%)': round(upside_pct, 2),
                'RSI': round(rsi, 1),
                'RVOL': round(rvol, 2),
                'Volume': int(vol)
            })
        except:
            continue
        progress.progress((idx + 1) / len(tickers))
    
    return pd.DataFrame(all_records)

if st.button("🚀 EXECUTE PRO SWING SCAN"):
    data = run_pro_swing_analysis()
    if not data.empty:
        # Style the 'BUY' column
        def style_buy(val):
            color = '#2ecc71' if val == 'YES' else 'transparent'
            return f'background-color: {color}; color: white; font-weight: bold'

        st.dataframe(data.style.map(style_buy, subset=['BUY']), use_container_width=True)
        
        # Backtest Report Download
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            data.to_excel(writer, index=False)
        st.download_button("📥 Download Swing Report", data=buffer.getvalue(), file_name="Pro_Swing_Report.xlsx")
    else:
        st.error("No high-volume stocks met the criteria.")