import streamlit as st
import pandas as pd
import requests
from sklearn.preprocessing import MinMaxScaler

st.title("Smart Portfolio: Value & Growth Picker")

investment_amount = st.number_input("Investment Amount ($)", value=500, step=100)
market_choice = st.selectbox("Select Stock Market Pool", ["US Only", "AU Only", "Mixed (US + AU)"])

ticker_dict = {
    "US Only": ["AAPL", "MSFT", "GOOGL", "TSLA"],
    "AU Only": ["CBA.AX", "BHP.AX", "WES.AX", "CSL.AX"],
    "Mixed (US + AU)": ["AAPL", "MSFT", "GOOGL", "TSLA", "CBA.AX", "BHP.AX", "WES.AX", "CSL.AX"]
}

tickers = ticker_dict[market_choice]
fmp_key = "rrRi5vJI4MPAQIH2k00JkyAanMZTRQkv"

@st.cache_data
def fetch_fundamentals(tickers, api_key):
    fundamentals = []
    for ticker in tickers:
        try:
            url = f"https://financialmodelingprep.com/api/v3/profile/{ticker}?apikey={api_key}"
            res = requests.get(url)
            data = res.json()
            if isinstance(data, list) and data:
                info = data[0]
                fundamentals.append({
                    "Ticker": ticker,
                    "Name": info.get("companyName", ticker),
                    "PE Ratio": info.get("peRatio", None),
                    "PB Ratio": info.get("priceToBookRatio", None),
                    "ROE": info.get("returnOnEquity", None),
                    "Debt/Equity": info.get("debtToEquity", None),
                    "EPS Growth": info.get("epsGrowth", None),
                    "Price": info.get("price", None)
                })
        except Exception as e:
            st.warning(f"Error loading {ticker}: {e}")
    return pd.DataFrame(fundamentals)

df = fetch_fundamentals(tickers, fmp_key)

st.subheader("Raw Fundamental Data")
st.dataframe(df)

if df.empty:
    st.warning("No data loaded into DataFrame.")
    st.stop()

try:
    features = df[["PE Ratio", "PB Ratio", "ROE", "Debt/Equity", "EPS Growth"]].copy()
    features = features.fillna(features.mean())
    features["PE Ratio"] = 1 / features["PE Ratio"]
    features["PB Ratio"] = 1 / features["PB Ratio"]
    features["Debt/Equity"] = 1 / features["Debt/Equity"]
    normalized = MinMaxScaler().fit_transform(features)
    df["Score"] = (normalized.mean(axis=1) * 100).round(2)

    # TEMP: No filter so we can confirm display works
    buy_signals = df.copy()
    total_score = buy_signals["Score"].sum()
    buy_signals["Allocation %"] = buy_signals["Score"] / total_score
    buy_signals["Investment ($)"] = (buy_signals["Allocation %"] * investment_amount).round(2)
    buy_signals["Est. Shares"] = (buy_signals["Investment ($)"] / buy_signals["Price"]).round(2)

    st.subheader("Buy Signals (No Filters)")
    st.dataframe(buy_signals[["Ticker", "Name", "Score", "Price", "Investment ($)", "Est. Shares"]])

except Exception as e:
    st.error(f"Scoring or display failed: {e}")
