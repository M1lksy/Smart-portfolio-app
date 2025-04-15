import streamlit as st
import pandas as pd
import requests
from sklearn.preprocessing import MinMaxScaler
import datetime
import yfinance as yf

st.set_page_config(layout="wide", page_title="Smart Portfolio")

# --- API KEYS ---
FINNHUB_KEY = "cvud0p9r01qjg1391glgcvud0p9r01qjg1391gm0"
ALPHA_KEY = "TPIRYXKQ80UVEUPR"
TIINGO_KEY = "9477b5815b1ab7e5283843beec9d0b4c152025d1"

# --- UI ---
st.title("Smart Portfolio: Value & Growth Picker")
investment_amount = st.number_input("Investment Amount ($)", value=500, step=100)
lump_sum = st.number_input("Initial Lump Sum ($)", value=10000, step=500)
years = st.slider("Years to Project", 1, 40, 20)
expected_return = st.slider("Expected Annual Return (%)", 1, 15, 7)
market_pool = st.selectbox("Select Market Pool", ["US Only", "AU Only", "Mixed (US + AU)"])

TICKERS = {
    "US Only": ["AAPL", "MSFT", "GOOGL", "TSLA"],
    "AU Only": ["BHP.AX", "WES.AX", "CSL.AX", "CBA.AX"],
    "Mixed (US + AU)": ["AAPL", "MSFT", "GOOGL", "TSLA", "BHP.AX", "WES.AX", "CSL.AX", "CBA.AX"]
}
tickers = TICKERS[market_pool]

SECTOR_MAP = {
    "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Communication Services", "TSLA": "Consumer Cyclical",
    "BHP.AX": "Materials", "WES.AX": "Consumer Defensive", "CSL.AX": "Healthcare", "CBA.AX": "Financials"
}
@st.cache_data
def fetch_stock_data(ticker):
    data = {"Ticker": ticker, "Source": [], "News": []}
    required = ["PE Ratio", "PB Ratio", "ROE", "Debt/Equity", "EPS Growth", "Price"]

    # --- Finnhub ---
    try:
        profile = requests.get(f"https://finnhub.io/api/v1/stock/profile2?symbol={ticker}&token={FINNHUB_KEY}").json()
        metrics = requests.get(f"https://finnhub.io/api/v1/stock/metric?symbol={ticker}&metric=all&token={FINNHUB_KEY}").json().get("metric", {})
        quote = requests.get(f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_KEY}").json()
        news = requests.get(f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from=2024-01-01&to=2025-01-01&token={FINNHUB_KEY}").json()

        data.update({
            "Name": profile.get("name", ""),
            "PE Ratio": metrics.get("peNormalizedAnnual"),
            "PB Ratio": metrics.get("pbAnnual"),
            "ROE": metrics.get("roeAnnual"),
            "Debt/Equity": metrics.get("totalDebt/totalEquityAnnual"),
            "EPS Growth": metrics.get("epsGrowth"),
            "Price": quote.get("c"),
            "News": news[:5]
        })
        data["Source"].append("Finnhub")
    except: pass

    # --- Tiingo Fallback ---
    try:
        tiingo_url = f"https://api.tiingo.com/tiingo/daily/{ticker.replace('.AX','')}/fundamentals?token={TIINGO_KEY}"
        tiingo = requests.get(tiingo_url).json()
        latest = tiingo.get("statementData", {}).get("latest", {})
        if latest:
            data["PE Ratio"] = data.get("PE Ratio") or latest.get("peRatio", {}).get("value")
            data["PB Ratio"] = data.get("PB Ratio") or latest.get("pbRatio", {}).get("value")
            data["ROE"] = data.get("ROE") or latest.get("roe", {}).get("value")
            data["Debt/Equity"] = data.get("Debt/Equity") or latest.get("debtEquityRatio", {}).get("value")
            data["EPS Growth"] = data.get("EPS Growth") or latest.get("epsGrowth", {}).get("value")
            data["Source"].append("Tiingo")
    except: pass

    # --- Alpha Vantage Fallback ---
    try:
        overview = requests.get(f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker}&apikey={ALPHA_KEY}").json()
        quote = requests.get(f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={ALPHA_KEY}").json()
        price = float(quote.get("Global Quote", {}).get("05. price", 0))

        data["Name"] = data.get("Name") or overview.get("Name", ticker)
        data["PE Ratio"] = data.get("PE Ratio") or float(overview.get("PERatio", 0))
        data["PB Ratio"] = data.get("PB Ratio") or float(overview.get("PriceToBookRatio", 0))
        data["ROE"] = data.get("ROE") or float(overview.get("ReturnOnEquityTTM", 0))
        data["Debt/Equity"] = data.get("Debt/Equity") or float(overview.get("DebtEquityRatio", 0))
        data["EPS Growth"] = data.get("EPS Growth") or float(overview.get("QuarterlyEarningsGrowthYOY", 0))
        data["Price"] = data.get("Price") or price
        data["Source"].append("Alpha Vantage")
    except: pass

    for key in required:
        if data.get(key) in [None, ""]:
            data[key] = None

    return data

@st.cache_data
def build_dataframe(ticker_list):
    rows = []
    for t in ticker_list:
        row = fetch_stock_data(t)
        if any(row[k] is not None for k in ["PE Ratio", "PB Ratio", "ROE", "Debt/Equity", "EPS Growth"]):
            row["Sector"] = SECTOR_MAP.get(t, "Unknown")
            rows.append(row)
    return pd.DataFrame(rows)

df = build_dataframe(tickers)
# --- Data Preview & Filtering ---
st.subheader("Raw Stock Data (partial data allowed)")
st.dataframe(df)

# --- Scoring Logic (Partial fields allowed) ---
features = df[["PE Ratio", "PB Ratio", "ROE", "Debt/Equity", "EPS Growth"]].copy()
features["PE Ratio"] = 1 / features["PE Ratio"]
features["PB Ratio"] = 1 / features["PB Ratio"]
features["Debt/Equity"] = 1 / features["Debt/Equity"]
features = features.fillna(features.mean())
normalized = MinMaxScaler().fit_transform(features)
df["Score"] = (normalized.mean(axis=1) * 100).round(2)

# --- Buy Recommendations ---
buy_df = df[df["Score"] >= 40].copy()
buy_df = buy_df.sort_values("Score", ascending=False)
total_score = buy_df["Score"].sum()
buy_df["Allocation %"] = buy_df["Score"] / total_score
buy_df["Investment ($)"] = (buy_df["Allocation %"] * investment_amount).round(2)
buy_df["Est. Shares"] = (buy_df["Investment ($)"] / buy_df["Price"]).fillna(0).astype(int)

# --- Display Buy Signals ---
st.subheader("Buy Signals")
if not buy_df.empty:
    st.dataframe(buy_df[["Ticker", "Name", "Score", "Price", "Investment ($)", "Est. Shares", "Sector", "Source"]])
    st.download_button("Download Buy Signals", data=buy_df.to_csv(index=False), file_name="buy_signals.csv", mime="text/csv")
else:
    st.warning("No qualifying stocks at this time.")

# --- Sector Breakdown ---
st.subheader("Sector Diversification")
sector_counts = buy_df["Sector"].value_counts()
st.bar_chart(sector_counts)
# --- Rebalancing Section ---
st.subheader("Rebalance Plan")
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
    return "HOLD"

buy_df["Action"] = buy_df.apply(lambda row: decide_action(row["Current Shares"], row["Target Shares"]), axis=1)
st.dataframe(buy_df[["Ticker", "Name", "Current Shares", "Target Shares", "Action"]])
rebalance_csv = buy_df[["Ticker", "Name", "Current Shares", "Target Shares", "Action"]].to_csv(index=False)
st.download_button("Download Rebalance Plan", data=rebalance_csv, file_name="rebalance_plan.csv", mime="text/csv")

# --- Projected Wealth ---
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
# --- Historical Backtesting ---
st.subheader("Backtest: Score vs. Price (5-Year View)")

def backtest_scores(ticker_list):
    price_data = {}
    for t in ticker_list:
        try:
            df_hist = yf.download(t, period="5y")["Adj Close"]
            price_data[t] = df_hist
        except:
            continue
    return pd.DataFrame(price_data)

price_df = backtest_scores(buy_df["Ticker"])
if not price_df.empty:
    st.line_chart(price_df)
    st.caption("5-year price history for current buy signals.")
else:
    st.warning("Unable to retrieve price history for selected stocks.")

# --- Final Dark Mode ---
st.markdown("""
<style>
html, body, [class*="css"] {
    background-color: #0E1117 !important;
    color: white !important;
}
.stDataFrame, .stTextInput, .stNumberInput, .stSelectbox, .stSlider {
    background-color: #1E222A !important;
    color: white !important;
}
</style>
""", unsafe_allow_html=True)