import streamlit as st
import pandas as pd
import requests
from sklearn.preprocessing import MinMaxScaler

# Set up the page
st.set_page_config(page_title="Smart Portfolio", layout="centered")
st.title("Smart Portfolio: Value & Growth Picker")

investment_amount = st.number_input("Investment Amount ($)", value=500, step=100)
market_choice = st.selectbox("Select Stock Market Pool", ["Mixed (US + AU)", "US Only", "AU Only"])

# Stock pools
us_stocks = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corp.",
    "GOOGL": "Alphabet Inc.",
    "TSLA": "Tesla Inc."
}

au_stocks = {
    "BHP": "BHP Group",
    "CBA": "Commonwealth Bank",
    "WES": "Wesfarmers Ltd",
    "CSL": "CSL Limited"
}

if market_choice == "US Only":
    tickers = us_stocks
elif market_choice == "AU Only":
    tickers = au_stocks
else:
    tickers = {**us_stocks, **au_stocks}

API_KEY = "rrRi5vJI4MPAQIH2k00JkyAanMZTRQkv"

@st.cache_data
def get_fundamentals(tickers):
    results = []
    for symbol, name in tickers.items():
        try:
            url = f"https://financialmodelingprep.com/api/v3/profile/{symbol}?apikey={API_KEY}"
            r = requests.get(url)
            if r.status_code != 200 or not r.json():
                continue
            info = r.json()[0]
            results.append({
                "Ticker": symbol,
                "Name": name,
                "PE Ratio": float(info.get("pe", "nan")),
                "PB Ratio": float(info.get("priceToBook", "nan")),
                "ROE": float(info.get("returnOnEquity", "nan")),
                "Debt/Equity": float(info.get("debtToEquity", "nan")),
                "EPS Growth": float(info.get("eps", "nan")),
                "Price": float(info.get("price", "nan"))
            })
        except Exception as e:
            st.warning(f"Error loading {symbol}: {e}")
    return pd.DataFrame(results)

df = get_fundamentals(tickers)
st.subheader("Raw Fundamental Data")
st.dataframe(df)

if df.empty:
    st.error("No stock data returned.")
    st.stop()

try:
    features = df[["PE Ratio", "PB Ratio", "ROE", "Debt/Equity", "EPS Growth"]].copy()
    features = features.fillna(features.mean(numeric_only=True))
    features["PE Ratio"] = 1 / features["PE Ratio"]
    features["PB Ratio"] = 1 / features["PB Ratio"]
    features["Debt/Equity"] = 1 / features["Debt/Equity"]

    normalized = MinMaxScaler().fit_transform(features)
    df["Score"] = (normalized.mean(axis=1) * 100).round(2)

    buy_signals = df.copy()
    total_score = buy_signals["Score"].sum()
    buy_signals["Allocation %"] = buy_signals["Score"] / total_score
    buy_signals["Investment ($)"] = (buy_signals["Allocation %"] * investment_amount).round(2)
    buy_signals["Est. Shares"] = (buy_signals["Investment ($)"] / buy_signals["Price"]).round(2)

    st.subheader("Buy Signals")
    st.dataframe(buy_signals[["Ticker", "Name", "Score", "Price", "Investment ($)", "Est. Shares"]])

    csv = buy_signals.to_csv(index=False)
    st.download_button("Download CSV", data=csv, file_name="buy_signals.csv", mime="text/csv")
except Exception as e:
    st.error(f"Error in scoring or display: {e}")
