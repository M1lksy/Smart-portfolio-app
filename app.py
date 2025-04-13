import streamlit as st
import pandas as pd
import requests
from sklearn.preprocessing import MinMaxScaler

st.title("Smart Portfolio: Value & Growth Picker")
investment_amount = st.number_input("Investment Amount ($)", value=500, step=100)

# Alpha Vantage API key
API_KEY = "KH2BI58UOLUJYVX1"

# Tickers to evaluate
tickers = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corp.",
    "GOOGL": "Alphabet Inc.",
    "TSLA": "Tesla Inc.",
    "CBA.AX": "Commonwealth Bank",
    "BHP.AX": "BHP Group",
    "WES.AX": "Wesfarmers Ltd",
    "CSL.AX": "CSL Limited"
}

# Function to fetch fundamentals
@st.cache_data
def get_fundamentals(tickers):
    data = []
    for symbol, name in tickers.items():
        try:
            url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={symbol}&apikey={API_KEY}"
            r = requests.get(url)
            if r.status_code != 200 or not r.text.startswith("{"):
                st.warning(f"API issue for {symbol}")
                continue
            info = r.json()
            data.append({
                "Ticker": symbol,
                "Name": name,
                "PE Ratio": float(info.get("PERatio", "nan")),
                "PB Ratio": float(info.get("PriceToBookRatio", "nan")),
                "ROE": float(info.get("ReturnOnEquityTTM", "nan")),
                "Debt/Equity": float(info.get("DebtEquityRatio", "nan")),
                "EPS Growth": float(info.get("QuarterlyEarningsGrowthYOY", "nan")),
            })
        except Exception as e:
            st.warning(f"Error fetching {symbol}: {e}")
            continue
    return pd.DataFrame(data)

df = get_fundamentals(tickers)

if df.empty:
    st.error("No data loaded into DataFrame.")
    st.stop()

# Scoring Logic
if not df.empty:
    features = df[["PE Ratio", "PB Ratio", "ROE", "Debt/Equity", "EPS Growth"]].copy()
    features = features.fillna(features.mean(numeric_only=True))

    # Invert ratios where lower is better
    features["PE Ratio"] = 1 / features["PE Ratio"]
    features["PB Ratio"] = 1 / features["PB Ratio"]
    features["Debt/Equity"] = 1 / features["Debt/Equity"]

    # Normalize and calculate score
    scaler = MinMaxScaler()
    normalized = scaler.fit_transform(features)
    df["Score"] = (normalized.mean(axis=1) * 100).round(2)

    # Loosen filter to allow more results
    buy_signals = df[df["Score"] >= 20].copy()
    buy_signals = buy_signals.sort_values("Score", ascending=False)

    # Allocate investment
    total_score = buy_signals["Score"].sum()
    buy_signals["Allocation %"] = buy_signals["Score"] / total_score
    buy_signals["Investment ($)"] = (buy_signals["Allocation %"] * investment_amount).round(2)
    buy_signals["Est. Shares"] = (buy_signals["Investment ($)"] / buy_signals["Price"]).round(2)

    # Display table
    st.subheader("Buy Signals")
    st.dataframe(buy_signals[["Ticker", "Name", "Score", "Price", "Investment ($)", "Est. Shares"]])

    # CSV download
    csv = buy_signals.to_csv(index=False)
    st.download_button("Download CSV", data=csv, file_name="buy_signals.csv", mime="text/csv")
else:
    st.warning("No data fetched — API may be rate-limited or temporarily down.")

# Filter buy signals
buy_signals = df[(df["Score"] >= 40) & (df["PE Ratio"] < 25)].copy()
buy_signals = buy_signals.sort_values("Score", ascending=False)

# Allocations
total_score = buy_signals["Score"].sum()
buy_signals["Allocation %"] = buy_signals["Score"] / total_score
buy_signals["Investment ($)"] = (buy_signals["Allocation %"] * investment_amount).round(2)

# Display
st.subheader("Buy Signals")
st.dataframe(buy_signals[["Ticker", "Name", "Score", "Investment ($)"]])

# Download
csv = buy_signals.to_csv(index=False)
st.download_button("Download CSV", data=csv, file_name="buy_signals.csv", mime="text/csv")
