import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import io
from concurrent.futures import ThreadPoolExecutor

# Streamlit Setup
st.set_page_config(page_title="AktienScreener by Christoph Winkelmann", layout="wide")

# Logo und Titel
try:
    st.image("logo.jpg", width=200)
except:
    pass

st.title("📊 AktienScreener by Christoph Winkelmann")
st.markdown("Automatisierter Scan von 750+ Aktien. **Copyright © Christoph Winkelmann**")

@st.cache_data(ttl=3600)
def fetch_tickers():
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        # S&P 500
        req_sp = requests.get('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies', headers=headers)
        sp = [str(t).replace('.', '-') for t in pd.read_html(io.StringIO(req_sp.text), attrs={'id': 'constituents'})[0]['Symbol'].tolist()]
        
        # Nasdaq 100
        req_ndq = requests.get('https://en.wikipedia.org/wiki/Nasdaq-100', headers=headers)
        ndq = [str(t).replace('.', '-') for t in pd.read_html(io.StringIO(req_ndq.text), attrs={'id': 'constituents'})[0]['Ticker'].tolist()]
        
        dax_etc = ["ADS.DE", "AIR.DE", "ALV.DE", "BAS.DE", "BAYN.DE", "BEI.DE", "BMW.DE", "BNR.DE", "CBK.DE", "CON.DE", 
                   "1COV.DE", "DTG.DE", "DBK.DE", "DB1.DE", "DHL.DE", "DTE.DE", "EOAN.DE", "FRE.DE", "FME.DE", "HNR1.DE", 
                   "HEI.DE", "HEN3.DE", "IFX.DE", "MBG.DE", "MRK.DE", "MTX.DE", "MUV2.DE", "PAH3.DE", "PUM.DE", "QIA.DE", 
                   "RHM.DE", "RWE.DE", "SAP.DE", "SRT3.DE", "SIE.DE", "ENR.DE", "SHL.DE", "SY1.DE", "VOW3.DE", "VNA.DE",
                   "AIXA.DE", "AT1.DE", "NDA.DE", "BC8.DE", "BFSA.DE", "GBF.DE", "AFX.DE", "EVD.DE", "DHER.DE", "LHA.DE", 
                   "EVK.DE", "EVT.DE", "FRA.DE", "FNTN.DE", "FPE3.DE", "G1A.DE", "GXI.DE", "HLE.DE", "HFG.DE", "HAG.DE", 
                   "KGX.DE", "KRN.DE", "LEG.DE", "NOEJ.DE", "NEM.DE", "PSM.DE", "SDF.DE", "WAF.DE", "CWC.DE", "EUZ.DE", 
                   "FIE.DE", "GFT.DE", "HBH.DE", "HYQ.DE", "JUN3.DE", "KCO.DE", "PNE3.DE", "SGL.DE", "S92.DE", "TLX.DE", 
                   "ZIL2.DE", "VOS.DE", "DUE.DE", "PFV.DE", "TTK.DE", "BVB.DE", "COK.DE", "DRW3.DE", "DWS.DE", "G24.DE", 
                   "KWS.DE", "MED.DE", "MKS.DE", "PBB.DE", "TKA.DE", "WCH.DE", "SMA.DE"]
        
        return list(set(sp + ndq + dax_etc))
    except:
        return ["AAPL", "MSFT", "AMZN"]

def scan_ticker(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="6mo")
        if len(df) < 50: return None
        
        # Indikatoren
        df['RSI'] = 100 - (100 / (1 + (df['Close'].diff().clip(lower=0).rolling(14).mean() / (-df['Close'].diff().clip(upper=0).rolling(14).mean()))))
        df['High_20Max'] = df['High'].shift(1).rolling(window=20).max()
        df['Vol_20SMA'] = df['Volume'].rolling(window=20).mean()
        df['TR'] = np.maximum(df['High'] - df['Low'], np.maximum(abs(df['High'] - df['Close'].shift(1)), abs(df['Low'] - df['Close'].shift(1))))
        df['ATR'] = df['TR'].rolling(window=14).mean()
        
        c_price = df['Close'].iloc[-1]
        signals = []
        if c_price > df['High_20Max'].iloc[-1]: signals.append("🚀 Breakout")
        if df['Volume'].iloc[-1] > (df['Vol_20SMA'].iloc[-1] * 2): signals.append("💥 Vol-Spike")
        
        if signals:
            name = stock.info.get('shortName', ticker)
            stop = c_price - (1.5 * df['ATR'].iloc[-1])
            return {
                "Ticker": ticker, "Unternehmen": name[:20], "Preis": round(c_price, 2),
                "Signale": " | ".join(signals), "ATR Stop": round(stop, 2),
                "Target": round(c_price + ((c_price - stop) * 2), 2),
                "Fazit": "🔥 Top Setup" if len(signals) > 1 else "🟢 Interessant"
            }
    except: return None

# UI
if st.button("🚀 Markt jetzt scannen"):
    with st.spinner("Scanner läuft..."):
        tickers = fetch_tickers()
        with ThreadPoolExecutor(max_workers=20) as executor:
            results = list(filter(None, executor.map(scan_ticker, tickers)))
    
    if results:
        df = pd.DataFrame(results)
        df = df.sort_values(by="Fazit", ascending=False)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Excel Download
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            # Copyright in A1
            worksheet = writer.book.add_worksheet('Screener Ergebnisse')
            worksheet.write('A1', 'Copyright © Christoph Winkelmann')
            # Daten ab Zeile 2
            df.to_excel(writer, sheet_name='Screener Ergebnisse', index=False, startrow=1)
            
        st.download_button("📥 Als Excel herunterladen", data=buffer, file_name="Screener_Christoph_Winkelmann.xlsx")
    else:
        st.write("Keine Signale gefunden.")