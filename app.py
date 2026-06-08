import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import io
import time
import plotly.graph_objects as go
from concurrent.futures import ThreadPoolExecutor

# --- LOGIN LOGIK ---
def check_password():
    def password_entered():
        if st.session_state["password"] == "nurderVfB":
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Passwort eingeben, um fortzufahren:", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Passwort falsch. Bitte erneut versuchen:", type="password", on_change=password_entered, key="password")
        st.error("❌ Zugriff verweigert")
        return False
    else:
        return True

# --- APP START ---
if check_password():
    st.set_page_config(page_title="Profi-Screener", layout="wide")

    # Logo & Titel
    col1, col2 = st.columns([1, 4])
    with col1:
        try: st.image("logo.jpg", width=200)
        except: st.write("Logo nicht gefunden.")
    with col2:
        st.title("📊 AktienScreener by Christoph Winkelmann")
        st.markdown("Copyright © Christoph Winkelmann | Profi-Analyse & Chart-Dashboard")

    # DOKUMENTATION
    with st.expander("ℹ️ Über den Screener (Methodik & Kriterien)", expanded=False):
        st.markdown("""
        ### 1. Daten-Universum & Marktabdeckung
        Der Screener analysiert über 750 Titel:
        - **USA:** S&P 500 & Nasdaq-100 (Blue-Chips & Tech-Werte).
        - **Deutschland:** DAX, MDAX, SDAX.
        
        ### 2. Screening-Kriterien (Trigger)
        - **🚀 Breakout:** Kurs übersteigt das 20-Tage-Hoch.
        - **💥 Volumen-Spike:** Volumen liegt > 50 % über dem 20-Tage-Schnitt.
        - **✨ Golden Cross:** EMA 50 hat kürzlich den EMA 200 nach oben gekreuzt (Langfristiges Trend-Signal).
        - **🔄 RSI Reversal:** RSI(14) dreht aus dem überverkauften Bereich (< 30) wieder nach oben.
        
        ### 3. Risiko-Management (ATR)
        - **Stop Loss:** Wird automatisch auf **1,5x ATR** unter den aktuellen Kurs gesetzt.
        - **Target:** Wird auf **3,0x ATR** über den Kurs gesetzt (CRV 1:2).
        """)

    @st.cache_data(ttl=3600)
    def fetch_tickers():
        tickers_dict = {}
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        try:
            tables = pd.read_html(io.StringIO(requests.get('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies', headers=headers).text))
            for df in tables:
                if 'Symbol' in df.columns and 'Security' in df.columns:
                    sp_dict = dict(zip(df['Symbol'].str.replace('.', '-'), df['Security']))
                    tickers_dict.update(sp_dict)
                    break
        except Exception: st.sidebar.warning("S&P 500 Liste teilweise nicht geladen.")

        try:
            tables = pd.read_html(io.StringIO(requests.get('https://en.wikipedia.org/wiki/Nasdaq-100', headers=headers).text))
            for df in tables:
                if 'Ticker' in df.columns and 'Company' in df.columns:
                    ndq_dict = dict(zip(df['Ticker'].str.replace('.', '-'), df['Company']))
                    tickers_dict.update(ndq_dict)
                    break
        except Exception: st.sidebar.warning("Nasdaq Liste teilweise nicht geladen.")

        deutschland = {
            "ADS.DE": "Adidas", "ALV.DE": "Allianz", "BAS.DE": "BASF", "BAYN.DE": "Bayer", "BMW.DE": "BMW", 
            "DBK.DE": "Deutsche Bank", "DHL.DE": "DHL Group", "DTE.DE": "Deutsche Telekom", "EOAN.DE": "E.ON", 
            "IFX.DE": "Infineon", "SAP.DE": "SAP", "SIE.DE": "Siemens", "VOW3.DE": "Volkswagen", "VNA.DE": "Vonovia",
            "RHM.DE": "Rheinmetall", "MUV2.DE": "Munich Re", "CBK.DE": "Commerzbank", "LHA.DE": "Lufthansa",
            "FRE.DE": "Fresenius", "HEI.DE": "Heidelberg Materials", "HEN3.DE": "Henkel", "MBG.DE": "Mercedes-Benz",
            "MRK.DE": "Merck", "MTX.DE": "MTU Aero", "PAH3.DE": "Porsche Holding", "PUM.DE": "Puma",
            "QIA.DE": "Qiagen", "RWE.DE": "RWE", "ENR.DE": "Siemens Energy", "SHL.DE": "Siemens Healthineers",
            "SY1.DE": "Symrise", "AIXA.DE": "Aixtron", "EVK.DE": "Evonik", "FRA.DE": "Fraport", "LEG.DE": "LEG Immobilien",
            "NDA.DE": "Aurubis", "FME.DE": "Fresenius Medical Care", "KRN.DE": "Krones", "WAF.DE": "Siltronic"
        }
        tickers_dict.update(deutschland)
        return tickers_dict

    # --- KOMPLETTER SCANNER INKLUSIVE RSI & GOLDEN CROSS ---
    def scan_ticker(item):
        ticker, name = item
        retries = 2
        for attempt in range(retries):
            try:
                stock = yf.Ticker(ticker)
                # WICHTIG: 1 Jahr Daten laden, damit der EMA 200 berechnet werden kann!
                df = stock.history(period="1y") 
                if len(df) < 200: return None
                
                # --- Indikatoren berechnen ---
                df['Vol_20SMA'] = df['Volume'].rolling(window=20).mean()
                c_price = df['Close'].iloc[-1]
                
                # ATR
                df['TR'] = np.maximum(df['High'] - df['Low'], np.maximum(abs(df['High'] - df['Close'].shift(1)), abs(df['Low'] - df['Close'].shift(1))))
                df['ATR'] = df['TR'].rolling(window=14).mean()
                atr = df['ATR'].iloc[-1]
                
                # EMAs
                df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
                df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
                
                # RSI (vereinfachte Wilder's Methode)
                delta = df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                df['RSI'] = 100 - (100 / (1 + rs))
                
                # --- Setup Bedingungen prüfen ---
                breakout = c_price > df['High'].shift(1).rolling(20).max().iloc[-1]
                vol_spike = df['Volume'].iloc[-1] > (df['Vol_20SMA'].iloc[-1] * 1.5)
                
                # Golden Cross: EMA 50 ist jetzt über EMA 200, war aber vor 3 Tagen noch drunter
                golden_cross = (df['EMA_50'].iloc[-1] > df['EMA_200'].iloc[-1]) and (df['EMA_50'].iloc[-3] <= df['EMA_200'].iloc[-3])
                
                # RSI Reversal: RSI war gestern unter 30 und ist heute darüber
                rsi_reversal = (df['RSI'].iloc[-2] < 30) and (df['RSI'].iloc[-1] >= 30)
                
                # Wenn auch nur EIN Signal zutrifft, Aktie anzeigen
                if breakout or vol_spike or golden_cross or rsi_reversal:
                    signals = []
                    if breakout: signals.append("🚀 Breakout")
                    if vol_spike: signals.append("💥 Vol-Spike")
                    if golden_cross: signals.append("✨ Golden Cross")
                    if rsi_reversal: signals.append("🔄 RSI Reversal")
                    
                    # Stop & Target
                    stop_loss = c_price - (1.5 * atr)
                    target = c_price + (3.0 * atr)
                    
                    return {
                        "Ticker": ticker, 
                        "Aktie": name,    
                        "Preis": round(c_price, 2), 
                        "Stop Loss": round(stop_loss, 2),
                        "Target": round(target, 2),
                        "Signale": " | ".join(signals), 
                        "Fazit": "🔥 Top Setup" if len(signals) > 1 else "🟢 Interessant"
                    }
                return None 
            except Exception:
                if attempt < retries - 1: time.sleep(1)
                else: return None

    # --- UI SCAN-BEREICH ---
    if "results" not in st.session_state: st.session_state["results"] = None
    
    col_btn, col_info = st.columns([1, 4])
    with col_btn:
        start_scan = st.button("🚀 Markt jetzt scannen")
        
    if start_scan:
        tickers_dict = fetch_tickers()
        st.write(f"Durchsuche {len(tickers_dict)} Aktien...") 
        progress_bar = st.progress(0)
        results = []
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            items = list(tickers_dict.items())
            future_to_item = {executor.submit(scan_ticker, item): item for item in items}
            for i, future in enumerate(future_to_item):
                res = future.result()
                if res: results.append(res)
                progress_bar.progress((i + 1) / len(items))
                
        st.session_state["results"] = pd.DataFrame(results)
    
    # --- INTERAKTIVE TABELLE & DEEP DIVE ---
    if st.session_state["results"] is not None and not st.session_state["results"].empty:
        df = st.session_state["results"]
        
        st.markdown("### 🎯 Ergebnisse (Klicke auf eine Zeile für Details)")
        
        event = st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",           
            selection_mode="single-row", 
            column_config={
                "Ticker": None,          
                "Aktie": st.column_config.TextColumn("Unternehmen", width="medium"),
                "Preis": st.column_config.NumberColumn("Preis", format="%.2f"),
                "Stop Loss": st.column_config.NumberColumn("Stop Loss", format="%.2f"),
                "Target": st.column_config.NumberColumn("Target", format="%.2f")
            }
        )
        
        if len(event.selection.rows) > 0:
            st.divider()
            selected_idx = event.selection.rows[0]
            selected_ticker = df.iloc[selected_idx]["Ticker"]
            selected_name = df.iloc[selected_idx]["Aktie"]
            
            with st.spinner(f"Lade Details für {selected_name}..."):
                stock_data = yf.Ticker(selected_ticker)
                
                info = {}
                for attempt in range(3):
                    try:
                        info = stock_data.info
                        if info: break
                    except: time.sleep(1)
                
                kgv = info.get('forwardPE', 'N/A') if info else 'N/A'
                mcap = info.get('marketCap', 0) if info else 0
                mcap_bn = f"{round(mcap / 1e9, 2)} Mrd." if mcap else 'N/A'
                
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Unternehmen", selected_name[:25])
                col_b.metric("Erw. KGV", kgv)
                col_c.metric("Marktkapitalisierung", mcap_bn)
            
                try:
                    # Chart muss nun auch auf 1y stehen für den EMA 200
                    df_chart = stock_data.history(period="1y")
                    df_chart['EMA_20'] = df_chart['Close'].ewm(span=20, adjust=False).mean()
                    df_chart['EMA_50'] = df_chart['Close'].ewm(span=50, adjust=False).mean()
                    df_chart['EMA_200'] = df_chart['Close'].ewm(span=200, adjust=False).mean()

                    fig = go.Figure(data=[go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'], name='Kurs')])
                    
                    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['EMA_20'], mode='lines', name='EMA 20', line=dict(color='cyan', width=1.5)))
                    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['EMA_50'], mode='lines', name='EMA 50', line=dict(color='orange', width=1.5)))
                    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['EMA_200'], mode='lines', name='EMA 200', line=dict(color='white', width=1.5, dash='dot')))

                    sl = df.iloc[selected_idx]["Stop Loss"]
                    tg = df.iloc[selected_idx]["Target"]
                    fig.add_hline(y=sl, line_dash="dash", line_color="red", annotation_text="Stop Loss")
                    fig.add_hline(y=tg, line_dash="dash", line_color="green", annotation_text="Target")

                    # Damit der Chart nicht zu gequetscht aussieht, zoomen wir auf die letzten 6 Monate,
                    # obwohl wir 1 Jahr geladen haben.
                    last_6_months = df_chart.index[-1] - pd.DateOffset(months=6)
                    fig.update_xaxes(range=[last_6_months, df_chart.index[-1]])

                    fig.update_layout(template="plotly_dark", title=f"Chartverlauf: {selected_name}")
                    st.plotly_chart(fig, use_container_width=True)
                except:
                    st.error("Chartdaten konnten aktuell nicht geladen werden.")
        else:
            st.info("👆 Klicke oben in der Tabelle auf eine Aktie, um die Chart-Details zu laden.")
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            worksheet = writer.book.add_worksheet('Screener Ergebnisse')
            worksheet.write('A1', 'Copyright © Christoph Winkelmann')
            df.drop(columns=["Ticker"]).to_excel(writer, sheet_name='Screener', index=False, startrow=1)
        st.download_button("📥 Excel-Bericht", data=buffer, file_name="Screener_Christoph_Winkelmann.xlsx")