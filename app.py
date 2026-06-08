import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import io
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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
    st.set_page_config(page_title="Profi-Screener", layout="wide", initial_sidebar_state="expanded")

    # ==========================================
    # SIDEBAR (Steuerung & Info)
    # ==========================================
    with st.sidebar:
        try: st.image("logo.jpg", use_container_width=True)
        except: pass
        
        st.title("📊 AktienScreener")
        st.markdown("© Christoph Winkelmann")
        st.divider()
        
        # Scannen Button
        start_scan = st.button("🚀 Markt jetzt scannen", use_container_width=True, type="primary")
        
        st.divider()
        
        # Dokumentation
        with st.expander("ℹ️ Methodik & Kriterien", expanded=False):
            st.markdown("""
            **1. Marktabdeckung**
            Scans von ca. 550 hochliquiden, einzigartigen Titeln (S&P 500, Nasdaq-100, DAX, MDAX, SDAX).
            
            **2. Trigger (Signale)**
            - **🚀 Breakout:** Kurs > 20-Tage-Hoch.
            - **💥 Volumen-Spike:** Volumen > 50% über 20T-Schnitt.
            - **✨ Golden Cross:** EMA 50 kreuzt EMA 200 nach oben.
            - **🔄 RSI Reversal:** RSI(14) dreht von <30 auf >=30.
            
            **3. Risiko-Management**
            - **Stop Loss:** 1,5x ATR unter Einstieg.
            - **Target:** 3,0x ATR über Einstieg (CRV 1:2).
            """)

    # ==========================================
    # FUNKTIONEN (Daten laden & scannen)
    # ==========================================
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
        except Exception: pass

        try:
            tables = pd.read_html(io.StringIO(requests.get('https://en.wikipedia.org/wiki/Nasdaq-100', headers=headers).text))
            for df in tables:
                if 'Ticker' in df.columns and 'Company' in df.columns:
                    ndq_dict = dict(zip(df['Ticker'].str.replace('.', '-'), df['Company']))
                    tickers_dict.update(ndq_dict)
                    break
        except Exception: pass

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

    def scan_ticker(item):
        ticker, name = item
        for attempt in range(2):
            try:
                stock = yf.Ticker(ticker)
                df = stock.history(period="1y") 
                if len(df) < 200: return None
                
                df['Vol_20SMA'] = df['Volume'].rolling(window=20).mean()
                c_price = df['Close'].iloc[-1]
                
                df['TR'] = np.maximum(df['High'] - df['Low'], np.maximum(abs(df['High'] - df['Close'].shift(1)), abs(df['Low'] - df['Close'].shift(1))))
                df['ATR'] = df['TR'].rolling(window=14).mean()
                atr = df['ATR'].iloc[-1]
                
                df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
                df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
                
                delta = df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                df['RSI'] = 100 - (100 / (1 + rs))
                
                breakout = c_price > df['High'].shift(1).rolling(20).max().iloc[-1]
                vol_spike = df['Volume'].iloc[-1] > (df['Vol_20SMA'].iloc[-1] * 1.5)
                golden_cross = (df['EMA_50'].iloc[-1] > df['EMA_200'].iloc[-1]) and (df['EMA_50'].iloc[-3] <= df['EMA_200'].iloc[-3])
                rsi_reversal = (df['RSI'].iloc[-2] < 30) and (df['RSI'].iloc[-1] >= 30)
                
                if breakout or vol_spike or golden_cross or rsi_reversal:
                    signals = []
                    if breakout: signals.append("🚀 Breakout")
                    if vol_spike: signals.append("💥 Vol-Spike")
                    if golden_cross: signals.append("✨ Golden Cross")
                    if rsi_reversal: signals.append("🔄 RSI Reversal")
                    
                    return {
                        "Ticker": ticker, 
                        "Aktie": name,    
                        "Preis": round(c_price, 2), 
                        "Stop Loss": round(c_price - (1.5 * atr), 2),
                        "Target": round(c_price + (3.0 * atr), 2),
                        "Signale": " | ".join(signals), 
                        "Fazit": "🔥 Top Setup" if len(signals) > 1 else "🟢 Interessant"
                    }
                return None 
            except Exception:
                if attempt < 1: time.sleep(1)
                else: return None

    # ==========================================
    # HAUPTBEREICH (Rechts)
    # ==========================================
    if "results" not in st.session_state: st.session_state["results"] = None
    if "scanned_total" not in st.session_state: st.session_state["scanned_total"] = 0
        
    if start_scan:
        tickers_dict = fetch_tickers()
        st.session_state["scanned_total"] = len(tickers_dict)
        
        with st.spinner(f"Durchsuche {len(tickers_dict)} Aktien..."):
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
    
    # --- ANZEIGE DER ERGEBNISSE ---
    if st.session_state["results"] is not None:
        df = st.session_state["results"]
        
        # 1. KPI DASHBOARD
        st.markdown("### 📈 Markt-Übersicht")
        col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
        col_kpi1.metric("Gescannt (Universum)", st.session_state["scanned_total"])
        col_kpi2.metric("Signale gefunden", len(df) if not df.empty else 0)
        
        top_setups = len(df[df['Fazit'] == '🔥 Top Setup']) if not df.empty else 0
        col_kpi3.metric("Top Setups 🔥", top_setups)
        
        st.divider()
        
        if not df.empty:
            st.markdown("### 🎯 Watchlist (Klicke auf eine Zeile für Details)")
            
            # 2. INTERAKTIVE TABELLE
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
                
                with st.spinner(f"Lade Profi-Chart für {selected_name}..."):
                    stock_data = yf.Ticker(selected_ticker)
                    
                    info = {}
                    for attempt in range(3):
                        try:
                            info = stock_data.info
                            if info: break
                        except: time.sleep(1)
                    
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric("Unternehmen", selected_name[:25])
                    col_b.metric("Erw. KGV", info.get('forwardPE', 'N/A') if info else 'N/A')
                    mcap = info.get('marketCap', 0) if info else 0
                    col_c.metric("Marktkapitalisierung", f"{round(mcap / 1e9, 2)} Mrd." if mcap else 'N/A')
                
                    try:
                        df_chart = stock_data.history(period="1y")
                        df_chart['EMA_20'] = df_chart['Close'].ewm(span=20, adjust=False).mean()
                        df_chart['EMA_50'] = df_chart['Close'].ewm(span=50, adjust=False).mean()
                        df_chart['EMA_200'] = df_chart['Close'].ewm(span=200, adjust=False).mean()

                        # 3. PROFI-CHART (SUBPLOTS: Kerzen oben, Volumen unten)
                        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                            vertical_spacing=0.03, row_heights=[0.7, 0.3])

                        # Oben: Kerzen & EMAs
                        fig.add_trace(go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'], name='Kurs'), row=1, col=1)
                        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['EMA_20'], mode='lines', name='EMA 20', line=dict(color='cyan', width=1.5)), row=1, col=1)
                        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['EMA_50'], mode='lines', name='EMA 50', line=dict(color='orange', width=1.5)), row=1, col=1)
                        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['EMA_200'], mode='lines', name='EMA 200', line=dict(color='white', width=1.5, dash='dot')), row=1, col=1)

                        sl = df.iloc[selected_idx]["Stop Loss"]
                        tg = df.iloc[selected_idx]["Target"]
                        fig.add_hline(y=sl, line_dash="dash", line_color="red", annotation_text="Stop Loss", row=1, col=1)
                        fig.add_hline(y=tg, line_dash="dash", line_color="green", annotation_text="Target", row=1, col=1)

                        # Unten: Volumen-Balken (Grün wenn Close > Open, sonst Rot)
                        colors = ['green' if row['Close'] >= row['Open'] else 'red' for index, row in df_chart.iterrows()]
                        fig.add_trace(go.Bar(x=df_chart.index, y=df_chart['Volume'], marker_color=colors, name='Volumen'), row=2, col=1)

                        # Design & Zoom (letzte 6 Monate anzeigen)
                        last_6_months = df_chart.index[-1] - pd.DateOffset(months=6)
                        fig.update_xaxes(range=[last_6_months, df_chart.index[-1]], rangeslider_visible=False)
                        
                        fig.update_layout(template="plotly_dark", title=f"Technische Analyse: {selected_name}", showlegend=False, height=600)
                        st.plotly_chart(fig, use_container_width=True)
                    except:
                        st.error("Chartdaten konnten aktuell nicht geladen werden.")
            else:
                st.info("👆 Klicke oben in der Tabelle auf eine Aktie, um die Chart-Details zu laden.")
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                writer.book.add_worksheet('Screener Ergebnisse').write('A1', 'Copyright © Christoph Winkelmann')
                df.drop(columns=["Ticker"]).to_excel(writer, sheet_name='Screener', index=False, startrow=1)
            st.sidebar.download_button("📥 Excel-Bericht laden", data=buffer, file_name="Screener_Christoph_Winkelmann.xlsx", use_container_width=True)
        else:
            st.info("Aktuell keine Signale gefunden. Der Markt bietet gerade keine Setups nach diesen strengen Kriterien.")
    else:
        st.info("👈 Klicke in der Seitenleiste auf 'Markt jetzt scannen', um die Analyse zu starten.")