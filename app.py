import streamlit as st
import pandas as pd
import yfinance as yf
from sklearn.preprocessing import MinMaxScaler

st.title("Smart Portfolio: Value & Growth Picker")
investment_amount = st.number_input("Investment Amount ($)", value=500, step=100)

# List of tickers
tickers = ["AAPL", "MSFT", "GOOGL", "TSLA", "CBA.AX", "BHP.AX", "WES.AX", "CSL.AX"]

# Function to load fundamentals and price; using caching for speed
@st.cache_data
def get_fundamentals(tickers):
    data = []
    for ticker in tickers:
        try:
            info = yf.Ticker(ticker).info
            price = yf.Ticker(ticker).history(period="1d")
            st.write(f"Fetched: {ticker}, Price rows: {len(price)}")
            data.append({
                "Ticker": ticker,
                "Name": info.get("shortName", ""),
                "PE Ratio": info.get("trailingPE", None),
                "PB Ratio": info.get("priceToBook", None),
                "ROE": info.get("returnOnEquity", None),
                "Debt/Equity": info.get("debtToEquity", None),
                "EPS Growth": info.get("earningsQuarterlyGrowth", None),
                "Price": price["Close"].iloc[-1] if not price.empty else None
            })
        except Exception as e:
            st.warning(f"Error fetching {ticker}: {e}")
            continue
    return pd.DataFrame(data)

# Load the data
df = get_fundamentals(tickers)

# Check if required columns exist
if not df.empty:
    required_cols = ["PE Ratio", "PB Ratio", "ROE", "Debt/Equity", "EPS Growth"]
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        st.error(f"Missing columns in data: {', '.join(missing_cols)}")
        st.stop()
else:
    st.error("No data loaded into DataFrame.")
    st.stop()

# Scoring Logic
features = df[["PE Ratio", "PB Ratio", "ROE", "Debt/Equity", "EPS Growth"]].copy()
features = features.fillna(features.mean())
features["PE Ratio"] = 1 / features["PE Ratio"]
features["PB Ratio"] = 1 / features["PB Ratio"]
features["Debt/Equity"] = 1 / features["Debt/Equity"]
normalized = MinMaxScaler().fit_transform(features)
df["Score"] = (normalized.mean(axis=1) * 100).round(2)

# Filter Buy Signals
buy_signals = df[(df["Score"] >= 40) & (df["PE Ratio"] < 25)].copy()
buy_signals = buy_signals.sort_values("Score", ascending=False)

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
