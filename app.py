import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import io
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

    # SCROLLBARE DOKUMENTATION
    with st.expander("ℹ️ Über den Screener (Methodik & Kriterien)", expanded=False):
        st.markdown("""
        <div style="height: 300px; overflow-y: scroll;">
        ### 1. Universum
        Der Screener durchsucht ca. 750 Titel aus:
        - **S&P 500:** US-Marktbreite.
        - **Nasdaq-100:** Tech- & Wachstumsfokus.
        - **DAX, MDAX, SDAX:** Umfassende Auswahl deutscher Unternehmen.
        
        ### 2. Screening-Kriterien
        - **🚀 Breakout:** Der aktuelle Kurs übersteigt das 20-Tage-Hoch. Ein klassisches Momentum-Signal.
        - **💥 Volumen-Spike:** Das Handelsvolumen liegt 50% über dem 20-Tage-Schnitt. Bestätigung durch institutionelles Interesse.
        
        ### 3. Fazit-Logik
        - **🟢 Interessant:** Eines der Kriterien erfüllt.
        - **🔥 Top Setup:** Beide Kriterien (Breakout + Volumen) gleichzeitig erfüllt.
        
        ### 4. Technische Hinweise
        Alle Daten werden via Yahoo Finance bezogen. Die Berechnung erfolgt in Echtzeit auf Basis der letzten 6 Monate.
        </div>
        """, unsafe_allow_html=True)

    @st.cache_data(ttl=3600)
    def fetch_tickers():
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            sp = [str(t).replace('.', '-') for t in pd.read_html(io.StringIO(requests.get('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies', headers=headers).text), attrs={'id': 'constituents'})[0]['Symbol'].tolist()]
            ndq = [str(t).replace('.', '-') for t in pd.read_html(io.StringIO(requests.get('https://en.wikipedia.org/wiki/Nasdaq-100', headers=headers).text), attrs={'id': 'constituents'})[0]['Ticker'].tolist()]
            deutschland = ["ADS.DE", "AIR.DE", "ALV.DE", "BAS.DE", "BAYN.DE", "BEI.DE", "BMW.DE", "BNR.DE", "CBK.DE", "CON.DE", "1COV.DE", "DTG.DE", "DBK.DE", "DB1.DE", "DHL.DE", "DTE.DE", "EOAN.DE", "FRE.DE", "FME.DE", "HNR1.DE", "HEI.DE", "HEN3.DE", "IFX.DE", "MBG.DE", "MRK.DE", "MTX.DE", "MUV2.DE", "PAH3.DE", "PUM.DE", "QIA.DE", "RHM.DE", "RWE.DE", "SAP.DE", "SRT3.DE", "SIE.DE", "ENR.DE", "SHL.DE", "SY1.DE", "VOW3.DE", "VNA.DE", "AIXA.DE", "AT1.DE", "NDA.DE", "BC8.DE", "BFSA.DE", "GBF.DE", "AFX.DE", "EVD.DE", "DHER.DE", "LHA.DE", "EVK.DE", "EVT.DE", "FRA.DE", "FNTN.DE", "FPE3.DE", "G1A.DE", "GXI.DE", "HLE.DE", "HFG.DE", "HAG.DE", "KGX.DE", "KRN.DE", "LEG.DE", "NOEJ.DE", "NEM.DE", "PSM.DE", "SDF.DE", "WAF.DE", "CWC.DE", "EUZ.DE", "FIE.DE", "GFT.DE", "HBH.DE", "HYQ.DE", "JUN3.DE", "KCO.DE", "PNE3.DE", "SGL.DE", "S92.DE", "TLX.DE", "ZIL2.DE", "VOS.DE", "DUE.DE", "PFV.DE", "TTK.DE", "BVB.DE", "COK.DE", "DRW3.DE", "DWS.DE", "G24.DE", "KWS.DE", "MED.DE", "MKS.DE", "PBB.DE", "TKA.DE", "WCH.DE", "SMA.DE"]
            return list(set(sp + ndq + deutschland))
        except: return ["AAPL", "MSFT", "NVDA"]

    def scan_ticker(ticker):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            df = stock.history(period="6mo")
            if len(df) < 50: return None
            df['Vol_20SMA'] = df['Volume'].rolling(window=20).mean()
            c_price = df['Close'].iloc[-1]
            breakout = c_price > df['High'].shift(1).rolling(20).max().iloc[-1]
            vol_spike = df['Volume'].iloc[-1] > (df['Vol_20SMA'].iloc[-1] * 1.5)
            if breakout or vol_spike:
                signals = ["🚀 Breakout"] if breakout else []
                if vol_spike: signals.append("💥 Vol-Spike")
                return {"Ticker": ticker, "Name": info.get('shortName', ticker)[:20], "KGV": info.get('forwardPE', 'N/A'), "MarketCap (B)": round(info.get('marketCap', 0) / 1e9, 2), "Preis": round(c_price, 2), "Signale": " | ".join(signals), "Fazit": "🔥 Top Setup" if len(signals) > 1 else "🟢 Interessant"}
        except: return None

    # UI SCAN-BEREICH MIT FORTSCHRITTSBALKEN
    if "results" not in st.session_state: st.session_state["results"] = None
    if st.button("🚀 Markt jetzt scannen"):
        tickers = fetch_tickers()
        progress_bar = st.progress(0)
        results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_ticker = {executor.submit(scan_ticker, t): t for t in tickers}
            for i, future in enumerate(future_to_ticker):
                res = future.result()
                if res: results.append(res)
                progress_bar.progress((i + 1) / len(tickers))
        st.session_state["results"] = pd.DataFrame(results)
    
    if st.session_state["results"] is not None and not st.session_state["results"].empty:
        st.dataframe(st.session_state["results"], use_container_width=True, hide_index=True)
        st.subheader("Chart-Analyse")
        selected = st.selectbox("Wähle eine Aktie:", st.session_state["results"]['Ticker'].unique())
        df_chart = yf.Ticker(selected).history(period="6mo")
        fig = go.Figure(data=[go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'])])
        fig.update_layout(template="plotly_dark", title=f"Chartverlauf: {selected}")
        st.plotly_chart(fig, use_container_width=True)