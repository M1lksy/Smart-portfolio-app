import streamlit as st
import pandas as pd
import requests
from sklearn.preprocessing import MinMaxScaler

st.set_page_config(layout="wide", page_title="Smart Portfolio")

API_KEY = "cvud0p9r01qjg1391glgcvud0p9r01qjg1391gm0"
BASE_URL = "https://finnhub.io/api/v1"

st.title("Smart Portfolio: Value & Growth Picker")

# User input
investment_amount = st.number_input("Investment Amount ($)", value=500, step=100)
market_pool = st.selectbox("Select Market Pool", ["US Only", "AU Only", "Mixed (US + AU)"])

# Ticker groups
TICKERS = {
    "US Only": ["AAPL", "MSFT", "GOOGL", "TSLA"],
    "AU Only": ["BHP.AX", "WES.AX", "CSL.AX", "CBA.AX"],
    "Mixed (US + AU)": ["AAPL", "MSFT", "GOOGL", "TSLA", "BHP.AX", "WES.AX", "CSL.AX", "CBA.AX"]
}

tickers = TICKERS[market_pool]
# Fetch fundamentals and prices from Finnhub
@st.cache_data
def fetch_fundamentals(ticker_list):
    results = []
    for symbol in ticker_list:
        try:
            profile_url = f"{BASE_URL}/stock/profile2?symbol={symbol}&token={API_KEY}"
            metrics_url = f"{BASE_URL}/stock/metric?symbol={symbol}&metric=all&token={API_KEY}"
            quote_url = f"{BASE_URL}/quote?symbol={symbol}&token={API_KEY}"
            news_url = f"{BASE_URL}/company-news?symbol={symbol}&from=2024-01-01&to=2025-01-01&token={API_KEY}"

            profile = requests.get(profile_url).json()
            metrics = requests.get(metrics_url).json().get("metric", {})
            quote = requests.get(quote_url).json()
            news = requests.get(news_url).json()

            results.append({
                "Ticker": symbol,
                "Name": profile.get("name", symbol),
                "PE Ratio": metrics.get("peNormalizedAnnual"),
                "PB Ratio": metrics.get("pbAnnual"),
                "ROE": metrics.get("roeAnnual"),
                "Debt/Equity": metrics.get("totalDebt/totalEquityAnnual"),
                "EPS Growth": metrics.get("epsGrowth"),
                "Price": quote.get("c"),
                "News": news[:5]  # Limit to latest 5
            })
        except Exception as e:
            st.warning(f"Error fetching {symbol}: {e}")
    return pd.DataFrame(results)

df = fetch_fundamentals(tickers)
# Display raw data
st.subheader("Raw Data")
st.dataframe(df)

# Check for missing data
required = ["PE Ratio", "PB Ratio", "ROE", "Debt/Equity", "EPS Growth", "Price"]
missing = [col for col in required if col not in df.columns]
if missing:
    st.warning(f"Missing columns: {', '.join(missing)}")
    st.stop()

# Drop rows missing required values
df = df.dropna(subset=required)
if df.empty:
    st.warning("No stocks have sufficient data to analyze. Try fewer tickers or wait for API reset.")
    st.stop()

# Scoring setup
features = df[["PE Ratio", "PB Ratio", "ROE", "Debt/Equity", "EPS Growth"]].copy()
features["PE Ratio"] = 1 / features["PE Ratio"]
features["PB Ratio"] = 1 / features["PB Ratio"]
features["Debt/Equity"] = 1 / features["Debt/Equity"]
features = features.fillna(features.mean())
if features.empty:
    st.warning("No valid data available to score stocks. Please try again later or check your API limits.")
    st.stop()
# Normalize and score
normalized = MinMaxScaler().fit_transform(features)
df["Score"] = (normalized.mean(axis=1) * 100).round(2)

# Buy filter
buy_df = df[df["Score"] >= 40].copy()
buy_df = buy_df.sort_values("Score", ascending=False)
total_score = buy_df["Score"].sum()
buy_df["Allocation %"] = buy_df["Score"] / total_score
buy_df["Investment ($)"] = (buy_df["Allocation %"] * investment_amount).round(2)
buy_df["Est. Shares"] = (buy_df["Investment ($)"] / buy_df["Price"]).fillna(0).astype(int)

# Display
st.subheader("Buy Signals")
if not buy_df.empty:
    st.dataframe(buy_df[["Ticker", "Name", "Score", "Price", "Investment ($)", "Est. Shares"]])
    st.download_button("Download CSV", data=buy_df.to_csv(index=False), file_name="buy_signals.csv", mime="text/csv")
else:
    st.warning("No qualifying stocks at this time.")
    # --- Rebalancing Logic ---
st.subheader("Rebalance Plan")
st.markdown("Enter your current holdings:")

current_shares = {}
for ticker in buy_df["Ticker"]:
    current_shares[ticker] = st.number_input(f"{ticker} - Current Shares", min_value=0, step=1, key=f"cur_{ticker}")

buy_df["Current Shares"] = buy_df["Ticker"].map(current_shares)
buy_df["Target Shares"] = buy_df["Est. Shares"]

def decide_action(current, target):
    if current < target:
        return f"BUY {target - current}"
    elif current > target:
        return f"SELL {current - target}"
    else:
        return "HOLD"

buy_df["Action"] = buy_df.apply(
    lambda row: decide_action(row["Current Shares"], row["Target Shares"]),
    axis=1
)

st.dataframe(buy_df[["Ticker", "Name", "Current Shares", "Target Shares", "Action"]])
rebalance_csv = buy_df[["Ticker", "Name", "Current Shares", "Target Shares", "Action"]].to_csv(index=False)
st.download_button("Download Rebalance Plan", data=rebalance_csv, file_name="rebalance_plan.csv", mime="text/csv")

# --- Projected Wealth ---
st.subheader("Projected Wealth Calculator")
years = st.slider("Years to Project", 1, 40, 20)
expected_return = st.slider("Expected Annual Return (%)", 1, 15, 7)
contribution = st.number_input("Fortnightly Contribution ($)", value=500, step=50)
lump_sum = st.number_input("Initial Lump Sum ($)", value=10000, step=500)

fv = lump_sum
growth = []
for year in range(1, years + 1):
    for _ in range(26):  # 26 fortnights
        fv = (fv + contribution) * (1 + (expected_return / 100) / 26)
    growth.append((year, round(fv, 2)))

df_growth = pd.DataFrame(growth, columns=["Year", "Projected Wealth ($)"])
st.line_chart(df_growth.set_index("Year"))
st.success(f"Projected value in {years} years: ${df_growth.iloc[-1]['Projected Wealth ($)']:,.2f}")
# --- Live News Section ---
st.subheader("Latest News by Stock")

for i, row in buy_df.iterrows():
    with st.expander(f"{row['Ticker']} News"):
        articles = row["News"]
        if articles:
            for article in articles:
                title = article.get("headline") or article.get("title")
                url = article.get("url")
                if title and url:
                    st.markdown(f"- [{title}]({url})")
        else:
            st.write("No recent news available.")
