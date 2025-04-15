import streamlit as st
import pandas as pd
import requests
from sklearn.preprocessing import MinMaxScaler

st.set_page_config(layout="wide", page_title="Smart Portfolio")

# --- API KEYS ---
FINNHUB_KEY = "cvud0p9r01qjg1391glgcvud0p9r01qjg1391gm0"
ALPHA_KEY = "TPIRYXKQ80UVEUPR"
FINNHUB_BASE = "https://finnhub.io/api/v1"
ALPHA_BASE = "https://www.alphavantage.co/query"

# --- Title & Inputs ---
st.title("Smart Portfolio: Value & Growth Picker")
investment_amount = st.number_input("Investment Amount ($)", value=500, step=100)
lump_sum = st.number_input("Initial Lump Sum ($)", value=10000, step=500)
years = st.slider("Years to Project", 1, 40, 20)
expected_return = st.slider("Expected Annual Return (%)", 1, 15, 7)
market_pool = st.selectbox("Select Market Pool", ["US Only", "AU Only", "Mixed (US + AU)"])

# --- Tickers ---
TICKERS = {
    "US Only": ["AAPL", "MSFT", "GOOGL", "TSLA"],
    "AU Only": ["BHP.AX", "WES.AX", "CSL.AX", "CBA.AX"],
    "Mixed (US + AU)": ["AAPL", "MSFT", "GOOGL", "TSLA", "BHP.AX", "WES.AX", "CSL.AX", "CBA.AX"]
}
tickers = TICKERS[market_pool]

@st.cache_data
def fetch_fundamentals(ticker_list):
    results = []
    for symbol in ticker_list:
        try:
            profile = requests.get(f"{FINNHUB_BASE}/stock/profile2?symbol={symbol}&token={FINNHUB_KEY}").json()
            metrics = requests.get(f"{FINNHUB_BASE}/stock/metric?symbol={symbol}&metric=all&token={FINNHUB_KEY}").json().get("metric", {})
            quote = requests.get(f"{FINNHUB_BASE}/quote?symbol={symbol}&token={FINNHUB_KEY}").json()
            news = requests.get(f"{FINNHUB_BASE}/company-news?symbol={symbol}&from=2024-01-01&to=2025-01-01&token={FINNHUB_KEY}").json()

            if not all([profile.get("name"), metrics.get("peNormalizedAnnual"), quote.get("c")]):
                raise ValueError("Missing Finnhub data")

            results.append({
                "Ticker": symbol,
                "Name": profile.get("name"),
                "PE Ratio": metrics.get("peNormalizedAnnual"),
                "PB Ratio": metrics.get("pbAnnual"),
                "ROE": metrics.get("roeAnnual"),
                "Debt/Equity": metrics.get("totalDebt/totalEquityAnnual"),
                "EPS Growth": metrics.get("epsGrowth"),
                "Price": quote.get("c"),
                "News": news[:5],
                "Source": "Finnhub"
            })

        except Exception:
            try:
                overview = requests.get(f"{ALPHA_BASE}?function=OVERVIEW&symbol={symbol}&apikey={ALPHA_KEY}").json()
                quote = requests.get(f"{ALPHA_BASE}?function=GLOBAL_QUOTE&symbol={symbol}&apikey={ALPHA_KEY}").json()
                price = float(quote.get("Global Quote", {}).get("05. price", 0))

                results.append({
                    "Ticker": symbol,
                    "Name": overview.get("Name", symbol),
                    "PE Ratio": float(overview.get("PERatio", 0)),
                    "PB Ratio": float(overview.get("PriceToBookRatio", 0)),
                    "ROE": float(overview.get("ReturnOnEquityTTM", 0)),
                    "Debt/Equity": float(overview.get("DebtEquityRatio", 0)),
                    "EPS Growth": float(overview.get("QuarterlyEarningsGrowthYOY", 0)),
                    "Price": price,
                    "News": [],
                    "Source": "Alpha Vantage"
                })
            except Exception:
                continue

    return pd.DataFrame(results)

df = fetch_fundamentals(tickers)

# --- Clean and Filter Data ---
required = ["PE Ratio", "PB Ratio", "ROE", "Debt/Equity", "EPS Growth", "Price"]
df = df.dropna(subset=required)

st.subheader("Raw Data")
st.dataframe(df)

if df.empty:
    st.warning("No stocks have complete data. Try again later or reduce ticker count.")
    st.stop()

# --- Scoring ---
features = df[["PE Ratio", "PB Ratio", "ROE", "Debt/Equity", "EPS Growth"]].copy()
features["PE Ratio"] = 1 / features["PE Ratio"]
features["PB Ratio"] = 1 / features["PB Ratio"]
features["Debt/Equity"] = 1 / features["Debt/Equity"]
features = features.fillna(features.mean())

if features.empty:
    st.warning("No valid data for scoring.")
    st.stop()

normalized = MinMaxScaler().fit_transform(features)
df["Score"] = (normalized.mean(axis=1) * 100).round(2)

# --- Buy Signal Filtering ---
buy_df = df[df["Score"] >= 40].copy()
buy_df = buy_df.sort_values("Score", ascending=False)
total_score = buy_df["Score"].sum()

buy_df["Allocation %"] = buy_df["Score"] / total_score
buy_df["Investment ($)"] = (buy_df["Allocation %"] * investment_amount).round(2)
buy_df["Est. Shares"] = (buy_df["Investment ($)"] / buy_df["Price"]).fillna(0).astype(int)

# --- Buy Signals Display ---
st.subheader("Buy Signals")
if not buy_df.empty:
    st.dataframe(buy_df[["Ticker", "Name", "Score", "Price", "Investment ($)", "Est. Shares", "Source"]])
    st.download_button("Download Buy Signals", data=buy_df.to_csv(index=False), file_name="buy_signals.csv", mime="text/csv")
else:
    st.warning("No qualifying stocks at this time.")

# --- Rebalancing Section ---
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

buy_df["Action"] = buy_df.apply(lambda row: decide_action(row["Current Shares"], row["Target Shares"]), axis=1)
st.dataframe(buy_df[["Ticker", "Name", "Current Shares", "Target Shares", "Action"]])
rebalance_csv = buy_df[["Ticker", "Name", "Current Shares", "Target Shares", "Action"]].to_csv(index=False)
st.download_button("Download Rebalance Plan", data=rebalance_csv, file_name="rebalance_plan.csv", mime="text/csv")

# --- Projected Wealth Calculator ---
st.subheader("Projected Wealth Calculator")
contribution = st.number_input("Fortnightly Contribution ($)", value=500, step=50)

future_value = lump_sum
history = []
for year in range(1, years + 1):
    for _ in range(26):
        future_value = (future_value + contribution) * (1 + (expected_return / 100) / 26)
    history.append((year, round(future_value, 2)))

df_growth = pd.DataFrame(history, columns=["Year", "Projected Wealth ($)"])
st.line_chart(df_growth.set_index("Year"))
st.success(f"Projected portfolio in {years} years: ${df_growth.iloc[-1]['Projected Wealth ($)']:,.2f}")

# --- News Section ---
st.subheader("Latest News by Stock")
for _, row in buy_df.iterrows():
    with st.expander(f"{row['Ticker']} News"):
        articles = row.get("News", [])
        if isinstance(articles, list) and articles:
            for article in articles:
                title = article.get("headline") or article.get("title")
                url = article.get("url")
                if title and url:
                    st.markdown(f"- [{title}]({url})")
        else:
            st.write("No recent news available.")

# --- Dark Mode Style ---
st.markdown("""
<style>
    .stApp {
        background-color: #0E1117;
        color: white;
    }
    .stButton>button {
        color: white;
    }
    .stTextInput>div>div>input, .stNumberInput>div>div>input {
        background-color: #1E222A;
        color: white;
    }
    .stSlider>div>div>div {
        background-color: #1E222A;
    }
    .stDataFrame {
        background-color: #1E222A;
    }
</style>
""", unsafe_allow_html=True)