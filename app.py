import streamlit as st
import pandas as pd
import requests
from sklearn.preprocessing import MinMaxScaler

# Dark theme and wide layout
st.set_page_config(layout="wide")

# Constants
API_KEY = "rrRi5vJI4MPAQIH2k00JkyAanMZTRQkv"
BASE_URL = "https://financialmodelingprep.com/api/v3"
STOCK_POOLS = {
    "US Only": ["AAPL", "MSFT", "GOOGL", "TSLA"],
    "AU Only": ["BHP.AX", "WES.AX", "CSL.AX"],
    "Mixed (US + AU)": ["AAPL", "MSFT", "GOOGL", "TSLA", "BHP.AX", "WES.AX", "CSL.AX"]
}

# Sidebar inputs
st.title("Smart Portfolio: Value & Growth Picker")
investment_amount = st.number_input("Enter Investment Amount ($)", value=500, step=100)
market_pool = st.selectbox("Select Stock Market Pool", list(STOCK_POOLS.keys()))

tickers = STOCK_POOLS[market_pool]
# Function to fetch financial data from FMP
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
# Show raw data
st.subheader("Raw Data")
st.dataframe(df)

# Filter out rows with missing values
df = df.dropna(subset=["PE Ratio", "PB Ratio", "ROE", "Debt/Equity", "EPS Growth", "Price"])

# Scoring Logic
features = df[["PE Ratio", "PB Ratio", "ROE", "Debt/Equity", "EPS Growth"]].copy()
features["PE Ratio"] = 1 / features["PE Ratio"]
features["PB Ratio"] = 1 / features["PB Ratio"]
features["Debt/Equity"] = 1 / features["Debt/Equity"]
features = features.fillna(features.mean())
normalized = MinMaxScaler().fit_transform(features)
df["Score"] = (normalized.mean(axis=1) * 100).round(2)

# Buy Signals (exclude PE > 25 to filter overvalued)
buy_signals = df[(df["Score"] >= 40) & (df["PE Ratio"] < 25)].copy()
buy_signals = buy_signals.sort_values("Score", ascending=False)

# Allocation & Shares
total_score = buy_signals["Score"].sum()
buy_signals["Allocation %"] = buy_signals["Score"] / total_score
buy_signals["Investment ($)"] = (buy_signals["Allocation %"] * investment_amount).round(2)
buy_signals["Est. Shares"] = (buy_signals["Investment ($)"] / buy_signals["Price"]).astype(int)

# Buy Table
st.subheader("Buy Signals")
if not buy_signals.empty:
    st.dataframe(buy_signals[["Ticker", "Name", "Score", "Price", "Investment ($)", "Est. Shares"]])
else:
    st.warning("No qualifying stocks at this time.")
        # CSV Export
    csv = buy_signals.to_csv(index=False)
    st.download_button("Download Buy Signals CSV", data=csv, file_name="buy_signals.csv", mime="text/csv")

    # Projected Wealth Calculator
    st.subheader("Projected Wealth Calculator")
    years = st.slider("Years to Project", 1, 40, 10)
    expected_return = st.slider("Expected Annual Return (%)", 1, 15, 7)
    contribution = st.number_input("Fortnightly Contribution ($)", value=500, step=50)

    future_value = 0
    for i in range(years * 26):
        future_value = (future_value + contribution) * (1 + (expected_return / 100) / 26)
    future_value = round(future_value, 2)

    st.success(f"Projected Wealth in {years} years: ${future_value:,}")

    # Rebalancing Logic
    st.subheader("Rebalance Plan")
    st.write("Enter your current holdings:")

    current_shares = {}
    for ticker in buy_signals["Ticker"]:
        current_shares[ticker] = st.number_input(f"Current shares of {ticker}", min_value=0, step=1, key=ticker)

    rebalance_df = buy_signals.copy()
    rebalance_df["Current Shares"] = rebalance_df["Ticker"].map(current_shares)
    rebalance_df["Target Shares"] = rebalance_df["Est. Shares"]
        def decide_action(current, target):
        if current < target:
            return f"BUY {target - current}"
        elif current > target:
            return f"SELL {current - target}"
        else:
            return "HOLD"

    rebalance_df["Action"] = rebalance_df.apply(
        lambda row: decide_action(row["Current Shares"], row["Target Shares"]), axis=1
    )

    st.dataframe(rebalance_df[["Ticker", "Name", "Current Shares", "Target Shares", "Action"]])
    rebalance_csv = rebalance_df[["Ticker", "Name", "Current Shares", "Target Shares", "Action"]].to_csv(index=False)
    st.download_button("Download Rebalance Plan", data=rebalance_csv, file_name="rebalance_plan.csv", mime="text/csv")

    # Optional: News headlines section (can be integrated if needed)
