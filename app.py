import streamlit as st
import pandas as pd
import requests
from sklearn.preprocessing import MinMaxScaler

st.set_page_config(layout="wide")
st.title("Smart Portfolio: Value & Growth Picker")

API_KEY = "rrRi5vJI4MPAQIH2k00JkyAanMZTRQkv"
BASE_URL = "https://financialmodelingprep.com/api/v3"

TICKERS = {
    "US Only": ["AAPL", "MSFT", "GOOGL", "TSLA"],
    "AU Only": ["BHP.AX", "WES.AX", "CSL.AX", "CBA.AX"],
    "Mixed (US + AU)": ["AAPL", "MSFT", "GOOGL", "TSLA", "BHP.AX", "WES.AX", "CSL.AX", "CBA.AX"]
}

investment_amount = st.number_input("Enter Investment Amount ($)", value=500, step=100)
market_pool = st.selectbox("Select Stock Market Pool", list(TICKERS.keys()))
tickers = TICKERS[market_pool]

@st.cache_data
def fetch_fundamentals(tickers):
    fundamentals = []
    for symbol in tickers:
        try:
            profile_url = f"{BASE_URL}/profile/{symbol}?apikey={API_KEY}"
            ratios_url = f"{BASE_URL}/ratios-ttm/{symbol}?apikey={API_KEY}"

            profile = requests.get(profile_url).json()
            ratios = requests.get(ratios_url).json()

            if not profile or not ratios:
                continue

            fundamentals.append({
                "Ticker": symbol,
                "Name": profile[0].get("companyName", ""),
                "PE Ratio": ratios[0].get("peRatioTTM"),
                "PB Ratio": ratios[0].get("priceToBookRatioTTM"),
                "ROE": ratios[0].get("returnOnEquityTTM"),
                "Debt/Equity": ratios[0].get("debtEquityRatioTTM"),
                "EPS Growth": ratios[0].get("epsGrowthTTM"),
                "Price": profile[0].get("price")
            })
        except Exception as e:
            st.warning(f"Error fetching {symbol}: {e}")
            continue
    return pd.DataFrame(fundamentals)

df = fetch_fundamentals(tickers)

st.subheader("Raw Data")
st.dataframe(df)

# --- Check if required columns exist ---
required_cols = ["PE Ratio", "PB Ratio", "ROE", "Debt/Equity", "EPS Growth", "Price"]
missing_cols = [col for col in required_cols if col not in df.columns]

if missing_cols:
    st.warning(f"Missing required data columns: {', '.join(missing_cols)}")
    st.stop()
else:
    df = df.dropna(subset=required_cols)

# --- Scoring Logic ---
features = df[["PE Ratio", "PB Ratio", "ROE", "Debt/Equity", "EPS Growth"]].copy()
features["PE Ratio"] = 1 / features["PE Ratio"]
features["PB Ratio"] = 1 / features["PB Ratio"]
features["Debt/Equity"] = 1 / features["Debt/Equity"]
features = features.fillna(features.mean())

normalized = MinMaxScaler().fit_transform(features)
df["Score"] = (normalized.mean(axis=1) * 100).round(2)

# --- Filter Buy Signals ---
buy_df = df[df["Score"] >= 40].copy()
buy_df = buy_df.sort_values("Score", ascending=False)

# --- Allocate and Estimate Shares ---
total_score = buy_df["Score"].sum()
buy_df["Allocation %"] = buy_df["Score"] / total_score
buy_df["Investment ($)"] = (buy_df["Allocation %"] * investment_amount).round(2)
buy_df["Est. Shares"] = (buy_df["Investment ($)"] / buy_df["Price"]).fillna(0).astype(int)

st.subheader("Buy Signals")
if not buy_df.empty:
    st.dataframe(buy_df[["Ticker", "Name", "Score", "Price", "Investment ($)", "Est. Shares"]])
    csv = buy_df.to_csv(index=False)
    st.download_button("Download Buy Signals CSV", data=csv, file_name="buy_signals.csv", mime="text/csv")
else:
    st.warning("No qualifying stocks at this time.")