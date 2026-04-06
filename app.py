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

    if 'DGNX' not in all_tickers: all_tickers.insert(0, 'DGNX')
    else:
        all_tickers.remove('DGNX'); all_tickers.insert(0, 'DGNX')

    found_setups = []
    dgnx_entry = None
    p_bar = st.progress(0)
    status = st.empty()
    
    for i, ticker in enumerate(all_tickers):
        if len(found_setups) >= 5 and dgnx_entry is not None:
            break
        
        status.text(f"Scanning Ticker {i}: {ticker} | Found: {len(found_setups)}/5")
        
        try:
            # DIRECT LINK TO STOOQ (Bypasses pandas_datareader)
            # US stocks need .us suffix in lowercase for the URL
            url = f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d"
            df = pd.read_csv(url)
            
            # Stooq returns: Date, Open, High, Low, Close, Volume
            if df.empty or len(df) < 60:
                continue

            # Ensure data is chronological (Stooq is usually fine, but safety first)
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.sort_values('Date')

            # --- Technical Calculations ---
            price = float(df['Close'].iloc[-1])
            sma_50 = float(df['Close'].rolling(window=50).mean().iloc[-1])
            
            # 20D VWAP
            df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
            df['PV'] = df['TP'] * df['Volume']
            vwap_20 = float(df['PV'].rolling(window=20).sum().iloc[-1] / df['Volume'].rolling(window=20).sum().iloc[-1])
            
            # RSI & RVOL
            rvol = float(df['Volume'].iloc[-1] / df['Volume'].rolling(window=60).mean().iloc[-1])
            rsi = float(calculate_rsi(df['Close']).iloc[-1])
            
            # ATR(14)
            tr = pd.concat([df['High'] - df['Low'], 
                            (df['High'] - df['Close'].shift()).abs(), 
                            (df['Low'] - df['Close'].shift()).abs()], axis=1).max(axis=1)
            atr_14 = float(tr.rolling(window=14).mean().iloc[-1])

            # --- Launchpad Filter ---
            is_buy = "YES" if (price > vwap_20 and price > sma_50 and 45 <= rsi <= 60 and rvol > 1.5) else "NO"
            
            setup = {
                'Ticker': ticker, 'BUY (YES)': is_buy, 'Entry': round(price, 2),
                'Take Profit': round(price + (3.5 * atr_14), 2), 'Stop Loss': round(price - (1.5 * atr_14), 2),
                '20D VWAP': round(vwap_20, 2), '50D SMA': round(sma_50, 2), 'RSI': round(rsi, 1),
                'RVOL': round(rvol, 2), '60D Avg Vol': int(df['Volume'].tail(60).mean())
            }

            if ticker == 'DGNX': dgnx_entry = setup
            if is_buy == "YES": found_setups.append(setup)
            
            time.sleep(0.1) # Respect Stooq's server

        except:
            continue
            
        p_bar.progress(min((i + 1) / len(all_tickers), 1.0))

    status.empty(); p_bar.empty()
    all_final = found_setups
    if dgnx_entry and not any(s['Ticker'] == 'DGNX' for s in all_final):
        all_final.append(dgnx_entry)
        
    return pd.DataFrame(all_final).sort_values(by=['BUY (YES)', 'RVOL'], ascending=[False, False]).head(6)