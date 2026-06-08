import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import io
import time  # NEU: Wichtig für den Auto-Retry!
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
        st.title("📊 Der AktienScreener von Chris Winkelmann")
        st.markdown("Copyright © ChrisWinkelmann | Profi-Analyse & Chart-Dashboard")

    # DOKUMENTATION
    with st.expander("ℹ️ Über den Screener (Methodik & Kriterien)", expanded=False):
        st.markdown("""
        ### 1. Daten-Universum & Marktabdeckung
        Der Screener analysiert ein breites Spektrum von über 750 Titeln, um eine ausgewogene Mischung aus Stabilität und Wachstumschancen zu gewährleisten:
        - **USA (S&P 500 & Nasdaq-100):** Fokus auf die liquidesten Blue-Chips und die führenden Technologie-Wachstumswerte.
        - **Deutschland (DAX, MDAX, SDAX):** Umfassende Abdeckung des deutschen Marktes, von den Schwergewichten bis zu den dynamischen Nebenwerten.
        
        ### 2. Screening-Kriterien
        - **🚀 Breakout:** Der aktuelle Kurs übersteigt das Hoch der letzten 20 Handelstage. Dieses Signal identifiziert Titel, die aus einer Konsolidierungsphase nach oben ausbrechen und relative Stärke zeigen.
        - **💥 Volumen-Spike:** Das heutige Handelsvolumen liegt mindestens 50 % über dem gleitenden 20-Tage-Durchschnitt. Dies dient als Bestätigung für erhöhtes institutionelles Interesse am aktuellen Preisniveau.
        
        ### 3. Fazit-Logik
        - **🟢 Interessant:** Mindestens eines der beiden technischen Kriterien wurde erfüllt. Ein Kandidat für die Watchlist.
        - **🔥 Top Setup:** Beide Kriterien (Breakout + Volumen-Spike) sind gleichzeitig erfüllt. Ein Signal mit hoher technischer Relevanz.
        
        ### 4. Technische Hinweise
        Die Daten werden in Echtzeit via Yahoo Finance API bezogen. Bitte beachte, dass dies ein technisches Analysetool ist und keine Anlageberatung darstellt.
        """)

    @st.cache_data(ttl=3600)
    def fetch_tickers():
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            sp = [str(t).replace('.', '-') for t in pd.read_html(io.StringIO(requests.get('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies', headers=headers).text), attrs={'id': 'constituents'})[0]['Symbol'].tolist()]
            ndq = [str(t).replace('.', '-') for t in pd.read_html(io.StringIO(requests.get('https://en.wikipedia.org/wiki/Nasdaq-100', headers=headers).text), attrs={'id': 'constituents'})[0]['Ticker'].tolist()]
            deutschland = ["ADS.DE", "AIR.DE", "ALV.DE", "BAS.DE", "BAYN.DE", "BEI.DE", "BMW.DE", "BNR.DE", "CBK.DE", "CON.DE", "1COV.DE", "DTG.DE", "DBK.DE", "DB1.DE", "DHL.DE", "DTE.DE", "EOAN.DE", "FRE.DE", "FME.DE", "HNR1.DE", "HEI.DE", "HEN3.DE", "IFX.DE", "MBG.DE", "MRK.DE", "MTX.DE", "MUV2.DE", "PAH3.DE", "PUM.DE", "QIA.DE", "RHM.DE", "RWE.DE", "SAP.DE", "SRT3.DE", "SIE.DE", "ENR.DE", "SHL.DE", "SY1.DE", "VOW3.DE", "VNA.DE", "AIXA.DE", "AT1.DE", "NDA.DE", "BC8.DE", "BFSA.DE", "GBF.DE", "AFX.DE", "EVD.DE", "DHER.DE", "LHA.DE", "EVK.DE", "EVT.DE", "FRA.DE", "FNTN.DE", "FPE3.DE", "G1A.DE", "GXI.DE", "HLE.DE", "HFG.DE", "HAG.DE", "KGX.DE", "KRN.DE", "LEG.DE", "NOEJ.DE", "NEM.DE", "PSM.DE", "SDF.DE", "WAF.DE", "CWC.DE", "EUZ.DE", "FIE.DE", "GFT.DE", "HBH.DE", "HYQ.DE", "JUN3.DE", "KCO.DE", "PNE3.DE", "SGL.DE", "S92.DE", "TLX.DE", "ZIL2.DE", "VOS.DE", "DUE.DE", "PFV.DE", "TTK.DE", "BVB.DE", "COK.DE", "DRW3.DE", "DWS.DE", "G24.DE", "KWS.DE", "MED.DE", "MKS.DE", "PBB.DE", "TKA.DE", "WCH.DE", "SMA.DE"]
            return list(set(sp + ndq + deutschland))
        except: return ["AAPL", "MSFT", "NVDA"]

    # --- SCHNELLER SCAN MIT AUTO-RETRY ---
    def scan_ticker(ticker):
        retries = 2 # Wenn Yahoo zickt, probieren wir es bis zu 2 Mal
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
                        "Ticker": ticker, 
                        "Preis": round(c_price, 2), 
                        "Signale": " | ".join(signals), 
                        "Fazit": "🔥 Top Setup" if len(signals) > 1 else "🟢 Interessant"
                    }
                # Wenn kein Fehler auftritt, aber einfach kein Signal da ist -> abbrechen
                return None 
            except Exception:
                if attempt < retries - 1:
                    time.sleep(1) # 1 Sekunde durchatmen, dann nächster Versuch
                else:
                    return None

    # --- UI SCAN-BEREICH ---
    if "results" not in st.session_state: st.session_state["results"] = None
    
    if st.button("🚀 Markt jetzt scannen"):
        tickers = fetch_tickers()
        progress_bar = st.progress(0)
        results = []
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            future_to_ticker = {executor.submit(scan_ticker, t): t for t in tickers}
            for i, future in enumerate(future_to_ticker):
                res = future.result()
                if res: results.append(res)
                progress_bar.progress((i + 1) / len(tickers))
                
        st.session_state["results"] = pd.DataFrame(results)
    
    # --- ERGEBNISSE & DEEP DIVE ---
    if st.session_state["results"] is not None and not st.session_state["results"].empty:
        st.dataframe(st.session_state["results"], use_container_width=True, hide_index=True)
        
        st.subheader("Chart & Detail-Analyse")
        selected = st.selectbox("Wähle eine Aktie für Details:", st.session_state["results"]['Ticker'].unique())
        
        if selected:
            with st.spinner(f"Lade Fundamentaldaten für {selected}..."):
                stock_data = yf.Ticker(selected)
                
                # Auto-Retry auch für die Fundamentaldaten
                info = {}
                for attempt in range(3):
                    try:
                        info = stock_data.info
                        if info: break
                    except:
                        time.sleep(1)
                
                name = info.get('shortName', selected) if info else selected
                kgv = info.get('forwardPE', 'N/A') if info else 'N/A'
                mcap = info.get('marketCap', 0) if info else 0
                mcap_bn = f"{round(mcap / 1e9, 2)} Mrd." if mcap else 'N/A'
                
                # Fundamentaldaten anzeigen
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Unternehmen", name[:25])
                col_b.metric("Erw. KGV", kgv)
                col_c.metric("Marktkapitalisierung", mcap_bn)
            
                # Chart mit EMA-Linien
                try:
                    df_chart = stock_data.history(period="6mo")
                    df_chart['EMA_20'] = df_chart['Close'].ewm(span=20, adjust=False).mean()
                    df_chart['EMA_50'] = df_chart['Close'].ewm(span=50, adjust=False).mean()

                    fig = go.Figure(data=[go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'], name='Kurs')])
                    
                    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['EMA_20'], mode='lines', name='EMA 20', line=dict(color='cyan', width=1.5)))
                    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['EMA_50'], mode='lines', name='EMA 50', line=dict(color='orange', width=1.5)))

                    fig.update_layout(template="plotly_dark", title=f"Chartverlauf: {name}")
                    st.plotly_chart(fig, use_container_width=True)
                except:
                    st.error("Chartdaten konnten aktuell nicht geladen werden. Bitte später erneut versuchen.")
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            worksheet = writer.book.add_worksheet('Screener Ergebnisse')
            worksheet.write('A1', 'Copyright © Christoph Winkelmann')
            st.session_state["results"].to_excel(writer, sheet_name='Screener Ergebnisse', index=False, startrow=1)
        st.download_button("📥 Excel-Bericht", data=buffer, file_name="Screener_Christoph_Winkelmann.xlsx")