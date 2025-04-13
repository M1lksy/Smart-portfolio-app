import streamlit as st
import pandas as pd
import yfinance as yf
from sklearn.preprocessing import MinMaxScaler

st.set_page_config(page_title="Smart Portfolio", layout="centered")
st.title("Smart Portfolio: Value & Growth Picker")

investment_amount = st.number_input("Investment Amount ($)", value=500, step=100)

# TEMP TEST - Confirm yfinance works before anything else runs
try:
    test_data = yf.Ticker("AAPL").history(period="1d")
    if test_data.empty:
        st.warning("yfinance API may be rate-limited or down.")
    else:
        st.caption("yfinance API is responding.")
except Exception as e:
    st.error(f"yfinance test failed: {e}")
    st.stop()

# List of tickers
tickers = ["AAPL", "MSFT", "GOOGL", "TSLA", "CBA.AX", "BHP.AX", "WES.AX", "CSL.AX"]

# Function to load fundamentals and price; using caching for speed
@st.cache_data
def get_fundamentals(tickers):
    data = []
    for ticker in tickers:
        try:
            info = yf.Ticker(ticker).info
            price_data = yf.Ticker(ticker).history(period="1d")
            if price_data.empty:
                raise ValueError("No price data returned")
            data.append({
                "Ticker": ticker,
                "Name": info.get("shortName", ticker),
                "PE Ratio": info.get("trailingPE", None),
                "PB Ratio": info.get("priceToBook", None),
                "ROE": info.get("returnOnEquity", None),
                "Debt/Equity": info.get("debtToEquity", None),
                "EPS Growth": info.get("earningsQuarterlyGrowth", None),
                "Price": price_data["Close"].iloc[-1]
            })
        except Exception as e:
            st.warning(f"Error fetching {ticker}: {e}")
    return pd.DataFrame(data)

df = get_fundamentals(tickers)

if df.empty:
    st.error("No data loaded into DataFrame.")
    st.stop()

# Check required columns
required_cols = ["PE Ratio", "PB Ratio", "ROE", "Debt/Equity", "EPS Growth"]
missing_cols = [col for col in required_cols if col not in df.columns]
if missing_cols:
    st.error(f"Missing columns in data: {', '.join(missing_cols)}")
    st.stop()

# Scoring Logic
features = df[required_cols].copy()
features = features.fillna(features.mean())

# Invert metrics where lower is better
features["PE Ratio"] = 1 / features["PE Ratio"]
features["PB Ratio"] = 1 / features["PB Ratio"]
features["Debt/Equity"] = 1 / features["Debt/Equity"]

# Normalize & Score
normalized = MinMaxScaler().fit_transform(features)
df["Score"] = (normalized.mean(axis=1) * 100).round(2)

# Filter Buy Signals
buy_signals = df[(df["Score"] >= 40) & (df["PE Ratio"] < 25)].copy()
buy_signals = buy_signals.sort_values("Score", ascending=False)

if buy_signals.empty:
    st.warning("No stocks meet the buy criteria today.")
    st.stop()

# Allocation & Estimated Shares
total_score = buy_signals["Score"].sum()
buy_signals["Allocation %"] = buy_signals["Score"] / total_score
buy_signals["Investment ($)"] = (buy_signals["Allocation %"] * investment_amount).round(2)
buy_signals["Est. Shares"] = (buy_signals["Investment ($)"] / buy_signals["Price"]).round(2)

# Display Output
st.subheader("Buy Signals")
st.dataframe(buy_signals[["Ticker", "Name", "Score", "Price", "Investment ($)", "Est. Shares"]])

# Download Option
csv = buy_signals.to_csv(index=False)
st.download_button("Download CSV", data=csv, file_name="buy_signals.csv", mime="text/csv")
