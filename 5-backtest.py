import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from backtesting import Backtest, Strategy

# --- 1. CONFIG & UI ---
st.set_page_config(page_title="5-Year Quant Lab", layout="wide")
st.title("🏛️ YM/NQ 5-Year Institutional Spike Analysis")

ticker_map = {
    "YM=F": "Dow Jones Futures",
    "NQ=F": "Nasdaq 100 Futures",
    "ES=F": "S&P 500 Futures",
    "RTY=F": "Russell 2000 Futures",
    "GC=F": "Gold Futures",
    "CL=F": "Crude Oil Futures"
}

ticker = st.sidebar.selectbox("Select Asset", list(ticker_map.keys()))
csv_upload = st.sidebar.file_uploader("Upload 15m_data.csv", type=["csv", "txt"])
z_thresh = st.sidebar.slider("Z-Score Sensitivity", 3.0, 10.0, 5.0, step=0.1)
hold_period = st.sidebar.number_input("Hold Duration (15m Bars)", 1, 50, 4)

# --- 2. THE DATA ENGINE ---
@st.cache_data
def load_and_sync(uploaded_file, ticker_choice):
    # Fetch Live Data (Last 60 days)
    try:
        live = yf.download(ticker_choice, period='60d', interval='15m', progress=False)
        if isinstance(live.columns, pd.MultiIndex): live.columns = live.columns.get_level_values(0)
        live = live.reset_index()
        live.columns = [str(col).lower() for col in live.columns]
        live.rename(columns={live.columns[0]: 'timestamp'}, inplace=True)
    except:
        live = pd.DataFrame()

    # Process Historical CSV
    if uploaded_file:
        hist = pd.read_csv(uploaded_file, sep='\t')
        hist.columns = [str(col).lower().strip() for col in hist.columns]
        
        # Datetime Normalization
        if 'datetime' in hist.columns:
            hist.rename(columns={'datetime': 'timestamp'}, inplace=True)
        elif 'date' in hist.columns and 'time' in hist.columns:
            hist['timestamp'] = hist['date'].astype(str) + ' ' + hist['time'].astype(str)
        
        hist['timestamp'] = pd.to_datetime(hist['timestamp'].str.replace('.', '-'), utc=True).dt.tz_convert('America/New_York')
        if 'tickvolume' in hist.columns: hist['volume'] = hist['tickvolume']
        
        # Merge
        df = pd.concat([hist, live]).drop_duplicates(subset=['timestamp']).sort_values('timestamp')
        return df
    return live

df = load_and_sync(csv_upload, ticker)

# --- 3. THE BACKTEST STRATEGY ---
def Z_SCORE_FUNC(series, window=100):
    s = pd.Series(series)
    return (s - s.rolling(window).mean()) / s.rolling(window).std()

class SpikeStrategy(Strategy):
    z_limit = z_thresh
    bars_to_hold = hold_period

    def init(self):
        self.zscore = self.I(Z_SCORE_FUNC, self.data.Volume)

    def next(self):
        # Time-based Exit Logic
        for trade in self.trades:
            if len(self.data) - trade.entry_bar >= self.bars_to_hold:
                trade.close()

        # Entry Logic
        if self.zscore[-1] > self.z_limit:
            # Bullish Spike (Close > Open)
            if self.data.Close[-1] > self.data.Open[-1]:
                sl_price = self.data.Low[-1] * 0.999 # tight stop
                tp_price = self.data.Close[-1] + (self.data.Close[-1] - sl_price) * 2.0
                self.buy(sl=sl_price, tp=tp_price)
            
            # Bearish Spike (Close < Open)
            elif self.data.Close[-1] < self.data.Open[-1]:
                sl_price = self.data.High[-1] * 1.001
                tp_price = self.data.Close[-1] - (sl_price - self.data.Close[-1]) * 2.0
                self.sell(sl=sl_price, tp=tp_price)

# --- 4. EXECUTION & DASHBOARD ---
if not df.empty:
    st.success(f"Successfully Loaded {len(df):,} bars.")
    
    # Prepare data for backtesting.py
    bt_data = df.copy()
    bt_data['timestamp'] = pd.to_datetime(bt_data['timestamp'])
    bt_data = bt_data.rename(columns={
        'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'
    }).set_index('timestamp')

    if st.button("🚀 Run Full 5-Year Backtest"):
        bt = Backtest(bt_data, SpikeStrategy, cash=100000, commission=.0002, margin=1/10)
        stats = bt.run()
        
        # Display Stats
        st.divider()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Final Equity", f"${stats['Equity Final [$]']:,.2f}")
        col2.metric("Win Rate", f"{stats['Win Rate [%]']:.2f}%")
        col3.metric("Total Trades", stats['# Trades'])
        col4.metric("Profit Factor", round(stats['Profit Factor'], 2))
        
        # Equity Curve Chart
        st.subheader("Cumulative Performance")
        st.line_chart(stats['_equity_curve']['Equity'])
        
        with st.expander("Detailed Stats"):
            st.write(stats)

    # Main Visualizer
    fig = go.Figure()
    fig.add_trace(go.Scattergl(x=df['timestamp'], y=df['close'], name="Price", line=dict(color='gold', width=1)))
    fig.update_layout(template="plotly_dark", height=500, xaxis_rangeslider_visible=True)
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Awaiting CSV upload to analyze historical institutional spikes...")
