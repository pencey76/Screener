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

    # Logo & Titel (Innerhalb des Logins, damit es sicher geladen wird)
    col1, col2 = st.columns([1, 4])
    with col1:
        try:
            st.image("logo.jpg", width=200)
        except:
            st.write("Logo nicht gefunden.")
    with col2:
        st.title("📊 AktienScreener by Christoph Winkelmann")
        st.markdown("Copyright © Christoph Winkelmann | Profi-Analyse & Chart-Dashboard")

    # DOKUMENTATION ALS EXPANDER
    with st.expander("ℹ️ Über den Screener (Methodik & Kriterien)"):
        st.markdown("""
        ### 1. Universum
        Der Screener durchsucht ca. 750 Titel aus dem **S&P 500**, **Nasdaq-100** und eine Auswahl an **DAX-Titeln**.
        
        ### 2. Screening-Kriterien
        * **🚀 Breakout:** Kurs übersteigt das 20-Tage-Hoch. Signal für relative Stärke.
        * **💥 Volumen-Spike:** Handelsvolumen liegt > 50% über dem 20-Tage-Durchschnitt. Indikator für institutionelles Interesse.
        
        ### 3. Fazit-Logik
        * **🟢 Interessant:** Eines der Kriterien erfüllt.
        * **🔥 Top Setup:** Beide Kriterien gleichzeitig erfüllt (Hohes Volumen bei Breakout).
        """)

    # --- Rest des Codes (Fetch, Scan, UI wie gehabt) ---
    @st.cache_data(ttl=3600)
    def fetch_tickers():
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            sp = [str(t).replace('.', '-') for t in pd.read_html(io.StringIO(requests.get('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies', headers=headers).text), attrs={'id': 'constituents'})[0]['Symbol'].tolist()]
            ndq = [str(t).replace('.', '-') for t in pd.read_html(io.StringIO(requests.get('https://en.wikipedia.org/wiki/Nasdaq-100', headers=headers).text), attrs={'id': 'constituents'})[0]['Ticker'].tolist()]
            dax = ["ADS.DE", "ALV.DE", "BAS.DE", "BAYN.DE", "BMW.DE", "DBK.DE", "DHL.DE", "DTE.DE", "EOAN.DE", "IFX.DE", "SAP.DE", "SIE.DE", "VOW3.DE", "VNA.DE"]
            return list(set(sp + ndq + dax))
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
                return {
                    "Ticker": ticker, "Name": info.get('shortName', ticker)[:20],
                    "KGV": info.get('forwardPE', 'N/A'), "MarketCap (B)": round(info.get('marketCap', 0) / 1e9, 2),
                    "Preis": round(c_price, 2), "Signale": " | ".join(signals),
                    "Fazit": "🔥 Top Setup" if len(signals) > 1 else "🟢 Interessant"
                }
        except: return None

    # UI Scan-Bereich
    if "results" not in st.session_state: st.session_state["results"] = None
    if st.button("🚀 Markt jetzt scannen"):
        with st.spinner("Analyse läuft..."):
            tickers = fetch_tickers()
            with ThreadPoolExecutor(max_workers=10) as executor:
                res = list(filter(None, executor.map(scan_ticker, tickers)))
                st.session_state["results"] = pd.DataFrame(res)
    
    if st.session_state["results"] is not None and not st.session_state["results"].empty:
        st.dataframe(st.session_state["results"], use_container_width=True, hide_index=True)
        # Chart & Export ... (restlicher Code wie gehabt)