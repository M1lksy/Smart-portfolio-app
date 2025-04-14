
import streamlit as st
import pandas as pd
import requests
from sklearn.preprocessing import MinMaxScaler

API_KEY = "rrRi5vJI4MPAQIH2k00JkyAanMZTRQkv"

TICKERS = {
    "US": ["AAPL", "MSFT", "GOOGL", "TSLA"],
    "AU": ["BHP.AX", "WES.AX", "CSL.AX", "CBA.AX"]
}

POOL_OPTIONS = {
    "US Only": TICKERS["US"],
    "AU Only": TICKERS["AU"],
    "Mixed (US + AU)": TICKERS["US"] + TICKERS["AU"]
}

FMP_BASE = "https://financialmodelingprep.com/api/v3"

def fetch_fundamentals(ticker):
    try:
        profile_url = f"{FMP_BASE}/profile/{ticker}?apikey={API_KEY}"
        ratios_url = f"{FMP_BASE}/ratios-ttm/{ticker}?apikey={API_KEY}"

        profile = requests.get(profile_url).json()
        ratios = requests.get(ratios_url).json()

        if not profile or not ratios:
            return None

        return {
            "Ticker": ticker,
            "Name": profile[0].get("companyName", ""),
            "PE Ratio": ratios[0].get("peRatioTTM"),
            "PB Ratio": ratios[0].get("pbRatioTTM"),
            "ROE": ratios[0].get("roeTTM"),
            "Debt/Equity": ratios[0].get("debtEquityRatioTTM"),
            "EPS Growth": ratios[0].get("epsGrowth"),
            "Price": profile[0].get("price")
        }
    except Exception:
        return None

st.set_page_config(page_title="Smart Portfolio", layout="centered")

st.title("Smart Portfolio: Value & Growth Picker")
investment_amount = st.number_input("Investment Amount ($)", value=500, step=100)
market_pool = st.selectbox("Select Stock Market Pool", list(POOL_OPTIONS.keys()))
tickers = POOL_OPTIONS[market_pool]

with st.spinner("Fetching data..."):
    data = [fetch_fundamentals(t) for t in tickers]
    df = pd.DataFrame([d for d in data if d])

if df.empty:
    st.warning("No qualifying stocks at this time.")
    st.stop()

st.subheader("Raw Data")
st.dataframe(df)

# Scoring
required_cols = ["PE Ratio", "PB Ratio", "ROE", "Debt/Equity", "EPS Growth"]
score_df = df[required_cols].copy()
score_df = score_df.apply(pd.to_numeric, errors="coerce")
score_df = score_df.fillna(score_df.mean())

score_df["PE Ratio"] = 1 / score_df["PE Ratio"]
score_df["PB Ratio"] = 1 / score_df["PB Ratio"]
score_df["Debt/Equity"] = 1 / score_df["Debt/Equity"]

scaler = MinMaxScaler()
normalized = scaler.fit_transform(score_df)
df["Score"] = normalized.mean(axis=1) * 100

# Filter & Allocate
buy_df = df[df["Score"] >= 40].copy()
buy_df = buy_df.sort_values("Score", ascending=False)
total_score = buy_df["Score"].sum()

if total_score > 0:
    buy_df["Allocation %"] = buy_df["Score"] / total_score
    buy_df["Investment ($)"] = (buy_df["Allocation %"] * investment_amount).round(2)
    buy_df["Est. Shares"] = (buy_df["Investment ($)"] / buy_df["Price"]).fillna(0).astype(int)
else:
    buy_df["Allocation %"] = 0
    buy_df["Investment ($)"] = 0
    buy_df["Est. Shares"] = 0

st.subheader("Buy Signals")
st.dataframe(buy_df[["Ticker", "Name", "Score", "Price", "Investment ($)", "Est. Shares"]])
st.download_button("Download CSV", data=buy_df.to_csv(index=False), file_name="buy_signals.csv")
