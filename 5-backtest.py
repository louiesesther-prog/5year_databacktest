import streamlit as st
import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy

# --- 1. INDICATOR FUNCTIONS (For tracking) ---
def Z_SCORE(volume_series, window=100):
    vol = pd.Series(volume_series)
    mean = vol.rolling(window).mean()
    std = vol.rolling(window).std()
    return (vol - mean) / std.replace(0, np.nan)

# --- 2. THE STRATEGY CLASS ---
class InstitutionalSpikeStrategy(Strategy):
    z_threshold = 5.0  # Adjustable threshold
    hold_bars = 4      # Time-based exit
    
    def init(self):
        # We calculate the Z-Score based on the Volume column
        self.zscore = self.I(Z_SCORE, self.data.Volume)

    def next(self):
        # Skip if we don't have enough data for the window
        if len(self.data) < 100:
            return

        # Current Price & Z-Score
        price = self.data.Close[-1]
        open_p = self.data.Open[-1]
        current_z = self.zscore[-1]

        # Close existing trades if they have been open for 'hold_bars'
        for trade in self.trades:
            if len(self.data) - trade.entry_bar >= self.hold_bars:
                trade.close()

        # --- ENTRY LOGIC ---
        if current_z > self.z_threshold:
            # BUY if it's a green spike
            if price > open_p:
                # Risk management: SL at the bottom of the spike candle
                risk = price - self.data.Low[-1]
                if risk > 0:
                    self.buy(sl=self.data.Low[-1], tp=price + (risk * 2.5))
            
            # SELL if it's a red spike
            elif price < open_p:
                risk = self.data.High[-1] - price
                if risk > 0:
                    self.sell(sl=self.data.High[-1], tp=price - (risk * 2.5))

# --- 3. STREAMLIT INTEGRATION ---
st.title("🔬 5-Year Strategy Backtester")

# Assume 'df' is your 5-year CSV data loaded earlier
# IMPORTANT: backtesting.py REQUIRES columns to be Capitalized (Open, High, Low, Close, Volume)
if 'df' in locals() or 'df' in globals():
    bt_df = df.copy()
    bt_df.columns = [c.capitalize() for c in bt_df.columns]
    bt_df = bt_df.set_index('Timestamp') # Ensure index is datetime

    if st.button("🚀 Run 5-Year Backtest"):
        bt = Backtest(bt_df, InstitutionalSpikeStrategy, 
                      cash=100_000, commission=.0002, margin=1/10)
        
        stats = bt.run()
        
        # Display Results
        col1, col2, col3 = st.columns(3)
        col1.metric("Final Equity", f"${stats['Equity Final [$]']:,.2f}")
        col2.metric("Win Rate", f"{stats['Win Rate [%]']:.2f}%")
        col3.metric("Profit Factor", f"{stats['Profit Factor']:.2f}")
        
        st.write(stats)
