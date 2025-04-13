import streamlit as st
import pandas as pd
import requests
from sklearn.preprocessing import MinMaxScaler

st.set_page_config(page_title="Smart Portfolio", layout="centered")
st.title("Smart Portfolio: Value & Growth Picker")

investment_amount = st.number_input("Investment Amount ($)", value=500, step=100)
market_choice = st.selectbox("Select Stock Market Pool", ["US Only", "AU Only", "Mixed (US + AU)"])

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
def get_fundamentals(ticker_dict):
    all_data = []
    for symbol, name in ticker_dict.items():
        try:
            profile_url = f"https://financialmodelingprep.com/api/v3/profile/{symbol}?apikey={API_KEY}"
            ratios_url = f"https://financialmodelingprep.com/api/v3/ratios-ttm/{symbol}?apikey={API_KEY}"
            growth_url = f"https://financialmodelingprep.com/api/v3/financial-growth/{symbol}?apikey={API_KEY}"

            profile = requests.get(profile_url).json()
            ratios = requests.get(ratios_url).json()
            growth = requests.get(growth_url).json()

            data = {
                "Ticker": symbol,
                "Name": name,
                "PE Ratio": float(ratios[0].get("peRatioTTM", "nan")) if ratios else None,
                "PB Ratio": float(ratios[0].get("priceToBookRatioTTM", "nan")) if ratios else None,
                "ROE": float(ratios[0].get("returnOnEquityTTM", "nan")) if ratios else None,
                "Debt/Equity": float(ratios[0].get("debtEquityRatioTTM", "nan")) if ratios else None,
                "EPS Growth": float(growth[0].get("epsgrowth", "nan")) if growth else None,
                "Price": float(profile[0].get("price", "nan")) if profile else None
            }
            all_data.append(data)
        except Exception as e:
            st.warning(f"Error fetching data for {symbol}: {e}")
    return pd.DataFrame(all_data)

df = get_fundamentals(tickers)
st.subheader("Raw Data")
st.dataframe(df)

if df.empty:
    st.error("No data available. Try a different stock pool or check API.")
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
    buy_signals["Est. Shares"] = (buy_signals["Investment ($)"] / buy_signals["Price"]).fillna(0).astype(int)

    st.subheader("Buy Signals")
    st.dataframe(buy_signals[["Ticker", "Name", "Score", "Price", "Investment ($)", "Est. Shares"]])

    csv = buy_signals.to_csv(index=False)
    st.download_button("Download Buy Signals", data=csv, file_name="buy_signals.csv", mime="text/csv")

    # Rebalance Section
    st.subheader("Rebalance Plan")
    st.markdown("Enter your current holdings:")

    rebalance_input = {}
    for ticker in buy_signals["Ticker"]:
        rebalance_input[ticker] = st.number_input(f"Current shares of {ticker}", min_value=0, value=0, step=1)

    buy_signals["Current Shares"] = buy_signals["Ticker"].map(rebalance_input)
    buy_signals["Target Shares"] = buy_signals["Est. Shares"]

    def rebalance_action(current, target):
        if current < target:
            return f"BUY {target - current}"
        elif current > target:
            return f"SELL {current - target}"
        else:
            return "HOLD"

    buy_signals["Action"] = buy_signals.apply(lambda row: rebalance_action(row["Current Shares"], row["Target Shares"]), axis=1)
    st.dataframe(buy_signals[["Ticker", "Name", "Current Shares", "Target Shares", "Action"]])

    rebalance_csv = buy_signals[["Ticker", "Name", "Current Shares", "Target Shares", "Action"]].to_csv(index=False)
    st.download_button("Download Rebalance Plan", data=rebalance_csv, file_name="rebalance_plan.csv", mime="text/csv")
except Exception as e:
    st.error(f"Error scoring or displaying data: {e}")

