import streamlit as st
import yfinance as yf
import pandas as pd
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
        Der Screener analysiert ein breites Spektrum von über 750 Titeln:
        - **USA (S&P 500 & Nasdaq-100):** Fokus auf die liquidesten Blue-Chips und Tech-Werte.
        - **Deutschland (DAX, MDAX, SDAX):** Umfassende Abdeckung, von Schwergewichten bis zu dynamischen Nebenwerten.
        
        ### 2. Screening-Kriterien
        - **🚀 Breakout:** Der aktuelle Kurs übersteigt das Hoch der letzten 20 Handelstage.
        - **💥 Volumen-Spike:** Das heutige Handelsvolumen liegt mindestens 50 % über dem 20-Tage-Durchschnitt.
        """)

    # ROBUSTERER LISTEN-DOWNLOAD MIT FIRMENNAMEN
    @st.cache_data(ttl=3600)
    def fetch_tickers():
        tickers_dict = {}
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        # S&P 500
        try:
            sp_df = pd.read_html(io.StringIO(requests.get('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies', headers=headers).text), attrs={'id': 'constituents'})[0]
            sp_dict = dict(zip(sp_df['Symbol'].str.replace('.', '-'), sp_df['Security']))
            tickers_dict.update(sp_dict)
        except Exception as e: st.sidebar.warning("S&P 500 Liste konnte nicht geladen werden.")

        # Nasdaq 100
        try:
            ndq_df = pd.read_html(io.StringIO(requests.get('https://en.wikipedia.org/wiki/Nasdaq-100', headers=headers).text), attrs={'id': 'constituents'})[0]
            ndq_dict = dict(zip(ndq_df['Ticker'].str.replace('.', '-'), ndq_df['Company']))
            tickers_dict.update(ndq_dict)
        except Exception as e: st.sidebar.warning("Nasdaq Liste konnte nicht geladen werden.")

        # Deutschland (Fest hinterlegt für maximale Stabilität inkl. Namen)
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

    # SCHNELLER SCAN (Erwartet jetzt Tuple aus Ticker und Name)
    def scan_ticker(item):
        ticker, name = item
        retries = 2
        for attempt in range(retries):
            try:
                stock = yf.Ticker(ticker)
                df = stock.history(period="6mo")
                if len(df) < 50: return None
                
                df['Vol_20SMA'] = df['Volume'].rolling(window=20).mean()
                c_price = df['Close'].iloc[-1]
                
                breakout = c_price > df['High'].shift(1).rolling(20).max().iloc[-1]
                vol_spike = df['Volume'].iloc[-1] > (df['Vol_20SMA'].iloc[-1] * 1.5)
                
                if breakout or vol_spike:
                    signals = ["🚀 Breakout"] if breakout else []
                    if vol_spike: signals.append("💥 Vol-Spike")
                    
                    return {
                        "Ticker": ticker, # Wird im Hintergrund behalten für den Chart
                        "Aktie": name,    # Wird dem Nutzer angezeigt
                        "Preis": round(c_price, 2), 
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
        progress_bar = st.progress(0)
        results = []
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            # Wir übergeben jetzt (Ticker, Name) an den Scanner
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
        
        # Die interaktive Tabelle!
        event = st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",           # Seite neu laden bei Klick
            selection_mode="single-row", # Nur eine Zeile gleichzeitig
            column_config={
                "Ticker": None,          # Ticker-Spalte komplett verstecken!
                "Aktie": st.column_config.TextColumn("Unternehmen", width="medium")
            }
        )
        
        # Wenn eine Zeile angeklickt wurde:
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
                
                # Fundamentaldaten
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Unternehmen", selected_name[:25])
                col_b.metric("Erw. KGV", kgv)
                col_c.metric("Marktkapitalisierung", mcap_bn)
            
                # Chart
                try:
                    df_chart = stock_data.history(period="6mo")
                    df_chart['EMA_20'] = df_chart['Close'].ewm(span=20, adjust=False).mean()
                    df_chart['EMA_50'] = df_chart['Close'].ewm(span=50, adjust=False).mean()

                    fig = go.Figure(data=[go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'], name='Kurs')])
                    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['EMA_20'], mode='lines', name='EMA 20', line=dict(color='cyan', width=1.5)))
                    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['EMA_50'], mode='lines', name='EMA 50', line=dict(color='orange', width=1.5)))

                    fig.update_layout(template="plotly_dark", title=f"Chartverlauf: {selected_name} ({selected_ticker})")
                    st.plotly_chart(fig, use_container_width=True)
                except:
                    st.error("Chartdaten konnten aktuell nicht geladen werden.")
        else:
            st.info("👆 Klicke oben in der Tabelle auf eine Aktie, um die Chart-Details zu laden.")
        
        # Excel Export (wie gehabt)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            worksheet = writer.book.add_worksheet('Screener Ergebnisse')
            worksheet.write('A1', 'Copyright © Christoph Winkelmann')
            df.drop(columns=["Ticker"]).to_excel(writer, sheet_name='Screener', index=False, startrow=1)
        st.download_button("📥 Excel-Bericht", data=buffer, file_name="Screener_Christoph_Winkelmann.xlsx")