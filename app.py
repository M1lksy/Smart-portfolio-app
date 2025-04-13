import streamlit as st
import pandas as pd
import requests
from sklearn.preprocessing import MinMaxScaler

# --- App title ---
st.set_page_config(page_title="Smart Portfolio", layout="centered")
st.title("Smart Portfolio: Value & Growth Picker")

# --- Investment input ---
investment_amount = st.number_input("Investment Amount ($)", value=500, step=100)

# --- Stock pool selection ---
market_choice = st.selectbox("Select Stock Market Pool", ["Mixed (US + AU)", "US Only", "AU Only"])

# --- Define tickers based on user choice ---
us_stocks = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corp.",
    "GOOGL": "Alphabet Inc.",
    "TSLA": "Tesla Inc."
}

au_stocks = {
    "BHP.AX": "BHP Group",
    "CBA.AX": "Commonwealth Bank",
    "WES.AX": "Wesfarmers Ltd",
    "CSL.AX": "CSL Limited"
}

if market_choice == "US Only":
    tickers = us_stocks
elif market_choice == "AU Only":
    tickers = au_stocks
else:
    tickers = {**us_stocks, **au_stocks}

# --- FMP API Key ---
API_KEY = "rrRi5vJI4MPAQIH2k00JkyAanMZTRQkv"

# --- Function to fetch data from FMP ---
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

            metrics = {
                "Ticker": symbol,
                "Name": name,
                "PE Ratio": float(info.get("pe", "nan")),
                "PB Ratio": float(info.get("priceToBook", "nan")),
                "ROE": float(info.get("returnOnEquity", "nan")),
                "Debt/Equity": float(info.get("debtToEquity", "nan")),
                "EPS Growth": float(info.get("eps", "nan")),
                "Price": float(info.get("price", "nan"))
            }
            results.append(metrics)
        except Exception as e:
            st.warning(f"Error fetching {symbol}: {e}")
            continue
    return pd.DataFrame(results)

# --- Load data ---
df = get_fundamentals(tickers)

# --- Check data ---
if df.empty:
    st.error("No stock data returned. Try switching markets or reloading.")
    st.stop()

# --- Scoring ---
features = df[["PE Ratio", "PB Ratio", "ROE", "Debt/Equity", "EPS Growth"]].copy()
features = features.fillna(features.mean(numeric_only=True))
features["PE Ratio"] = 1 / features["PE Ratio"]
features["PB Ratio"] = 1 / features["PB Ratio"]
features["Debt/Equity"] = 1 / features["Debt/Equity"]

normalized = MinMaxScaler().fit_transform(features)
df["Score"] = (normalized.mean(axis=1) * 100).round(2)

# --- Filter buy signals ---
buy_signals = df[(df["Score"] >= 0)].copy()
buy_signals = buy_signals.sort_values("Score", ascending=False)

if buy_signals.empty:
    st.warning("No qualifying stocks at this time.")
    st.stop()

# --- Allocation ---
total_score = buy_signals["Score"].sum()
buy_signals["Allocation %"] = buy_signals["Score"] / total_score
buy_signals["Investment ($)"] = (buy_signals["Allocation %"] * investment_amount).round(2)
buy_signals["Est. Shares"] = (buy_signals["Investment ($)"] / buy_signals["Price"]).round(2)

# --- Display ---
st.subheader("Recommended Buy Signals")
st.dataframe(buy_signals[["Ticker", "Name", "Score", "Price", "Investment ($)", "Est. Shares"]])

# --- CSV Download ---
csv = buy_signals.to_csv(index=False)
st.download_button("Download CSV", data=csv, file_name="buy_signals.csv", mime="text/csv")
