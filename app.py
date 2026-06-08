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

    st.title("📊 AktienScreener by Christoph Winkelmann")
    st.markdown("Copyright © Christoph Winkelmann | Profi-Analyse & Chart-Dashboard")

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
            
            df['RSI'] = 100 - (100 / (1 + (df['Close'].diff().clip(lower=0).rolling(14).mean() / (-df['Close'].diff().clip(upper=0).rolling(14).mean()))))
            df['Vol_20SMA'] = df['Volume'].rolling(window=20).mean()
            c_price = df['Close'].iloc[-1]
            
            signals = []
            if c_price > df['High'].shift(1).rolling(20).max().iloc[-1]: signals.append("🚀 Breakout")
            if df['Volume'].iloc[-1] > (df['Vol_20SMA'].iloc[-1] * 2): signals.append("💥 Vol-Spike")
            
            if signals:
                return {
                    "Ticker": ticker, "Name": info.get('shortName', ticker)[:20],
                    "KGV": info.get('forwardPE', 'N/A'), "MarketCap (B)": round(info.get('marketCap', 0) / 1e9, 2),
                    "Preis": round(c_price, 2), "Signale": " | ".join(signals),
                    "Fazit": "🔥 Top Setup" if len(signals) > 1 else "🟢 Interessant"
                }
        except: return None

    # UI Bereich
    if st.button("🚀 Markt jetzt scannen"):
        with st.spinner("Analyse läuft..."):
            tickers = fetch_tickers()
            with ThreadPoolExecutor(max_workers=20) as executor:
                results = list(filter(None, executor.map(scan_ticker, tickers)))
        
        if results:
            df = pd.DataFrame(results)
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            st.subheader("Chart-Analyse")
            selected = st.selectbox("Wähle eine Aktie für den Chart:", df['Ticker'].unique())
            df_chart = yf.Ticker(selected).history(period="6mo")
            fig = go.Figure(data=[go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'])])
            fig.update_layout(template="plotly_dark", title=f"Chartverlauf: {selected}")
            st.plotly_chart(fig, use_container_width=True)
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                worksheet = writer.book.add_worksheet('Screener Ergebnisse')
                worksheet.write('A1', 'Copyright © Christoph Winkelmann')
                df.to_excel(writer, sheet_name='Screener Ergebnisse', index=False, startrow=1)
            st.download_button("📥 Excel-Bericht", data=buffer, file_name="Screener_Christoph_Winkelmann.xlsx")
        else:
            st.warning("Keine Signale gefunden.")