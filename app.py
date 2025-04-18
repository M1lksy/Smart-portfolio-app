import streamlit as st
import pandas as pd
import requests
import yfinance as yf
import time
from datetime import datetime
from sklearn.preprocessing import MinMaxScaler

# --- Streamlit Setup ---
st.set_page_config(layout="wide", page_title="Smart Portfolio")

# --- API Keys ---
FINNHUB_KEY = "cvud0p9r01qjg1391glgcvud0p9r01qjg1391gm0"
ALPHA_KEY = "TPIRYXKQ80UVEUPR"
TIINGO_KEY = "9477b5815b1ab7e5283843beec9d0b4c152025d1"
MARKETSTACK_KEY = "84d35de2d7d3c225b77b712bc6ea1725"

# --- Time Sync (WorldTimeAPI) ---
@st.cache_data(ttl=60)
def get_townsville_time():
    try:
        r = requests.get("https://worldtimeapi.org/api/timezone/Australia/Brisbane", timeout=10).json()
        return datetime.fromisoformat(r["datetime"].split(".")[0]).strftime("%H:%M:%S")
    except:
        return "Unavailable"

current_time = get_townsville_time()
st.markdown(f"**Townsville Time (synced):** `{current_time}`")

# --- Inputs ---
st.title("Smart Portfolio: Value & Growth Picker")
investment_amount = st.number_input("Investment Amount ($)", value=500, step=100)
lump_sum = st.number_input("Initial Lump Sum ($)", value=10000, step=500)
years = st.slider("Years to Project", 1, 40, 20)
expected_return = st.slider("Expected Annual Return (%)", 1, 15, 7)
market_pool = st.selectbox("Select Market Pool", ["US Only", "AU Only", "Mixed (US + AU)"])
avoid_sector_overload = st.toggle("Avoid Sector Overload")
show_watchlist = st.toggle("Enable Watchlist Mode")

# --- Tickers ---
TICKERS = {
    "US Only": ["AAPL", "MSFT", "GOOGL", "TSLA"],
    "AU Only": ["BHP.AX", "WES.AX", "CSL.AX", "CBA.AX"],
    "Mixed (US + AU)": ["AAPL", "MSFT", "GOOGL", "TSLA", "BHP.AX", "WES.AX", "CSL.AX", "CBA.AX"]
}
tickers = TICKERS[market_pool]

SECTOR_MAP = {
    "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Communication",
    "TSLA": "Consumer Cyclical", "BHP.AX": "Materials", "WES.AX": "Consumer Defensive",
    "CSL.AX": "Healthcare", "CBA.AX": "Financials"
}

# --- Dark Red & Black Theme Fix ---
st.markdown("""
<style>
/* Global base */
html, body, [class*="css"] {
    background-color: #0E0E0E !important;
    color: #EDEDED !important;
}

/* Main containers */
[data-testid="stAppViewContainer"], [data-testid="stHeader"], [data-testid="stSidebar"] {
    background-color: #0E0E0E !important;
}

/* Input fields & widgets */
.stTextInput input,
.stNumberInput input,
.stSelectbox div,
.stSlider > div,
.stTextArea textarea,
.css-1cpxqw2, .css-1wa3eu0-placeholder {
    background-color: #1B1B1B !important;
    color: white !important;
    border-color: #911C1C !important;
}

/* DataFrame tables */
.stDataFrame, .stDataFrame div, .stDataFrame td, .stDataFrame th {
    background-color: #111111 !important;
    color: #EDEDED !important;
}

/* Buttons */
.stButton > button,
.stDownloadButton > button {
    background-color: #B22222 !important;
    color: white !important;
    border: 1px solid #911C1C !important;
}

/* Sliders */
.stSlider > div > div > div {
    background: #911C1C !important;
}

/* Expanders */
.stExpander, .stExpanderHeader {
    background-color: #1B1B1B !important;
    color: white !important;
    border: 1px solid #3A3A3A !important;
}

/* Section titles */
h1, h2, h3, h4 {
    color: #FF4C4C !important;
}
</style>
""", unsafe_allow_html=True)

@st.cache_data
def fetch_stock_data(ticker):
    data = {"Ticker": ticker, "Source": [], "News": []}
    required = ["PE Ratio", "PB Ratio", "ROE", "Debt/Equity", "EPS Growth", "Price"]

    try:
        profile = safe_request(f"https://finnhub.io/api/v1/stock/profile2?symbol={ticker}&token={FINNHUB_KEY}")
        metrics = safe_request(f"https://finnhub.io/api/v1/stock/metric?symbol={ticker}&metric=all&token={FINNHUB_KEY}").get("metric", {})
        quote = safe_request(f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_KEY}")
        raw_news = safe_request(f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from=2024-01-01&to=2025-01-01&token={FINNHUB_KEY}")
        clean_news = [{"title": n.get("headline", ""), "url": n.get("url", "")} for n in raw_news[:5] if n.get("url")]

        data.update({
            "Name": profile.get("name", ""),
            "PE Ratio": metrics.get("peNormalizedAnnual"),
            "PB Ratio": metrics.get("pbAnnual"),
            "ROE": metrics.get("roeAnnual"),
            "Debt/Equity": metrics.get("totalDebt/totalEquityAnnual"),
            "EPS Growth": metrics.get("epsGrowth"),
            "Price": quote.get("c"),
            "News": clean_news
        })
        data["Source"].append("Finnhub")
    except: pass

    try:
        tiingo = safe_request(f"https://api.tiingo.com/tiingo/daily/{ticker.replace('.AX','')}/fundamentals?token={TIINGO_KEY}")
        latest = tiingo.get("statementData", {}).get("latest", {})
        if latest:
            data["PE Ratio"] = data.get("PE Ratio") or latest.get("peRatio", {}).get("value")
            data["PB Ratio"] = data.get("PB Ratio") or latest.get("pbRatio", {}).get("value")
            data["ROE"] = data.get("ROE") or latest.get("roe", {}).get("value")
            data["Debt/Equity"] = data.get("Debt/Equity") or latest.get("debtEquityRatio", {}).get("value")
            data["EPS Growth"] = data.get("EPS Growth") or latest.get("epsGrowth", {}).get("value")
            data["Source"].append("Tiingo")
    except: pass

    try:
        ov = safe_request(f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker}&apikey={ALPHA_KEY}")
        quote = safe_request(f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={ALPHA_KEY}")
        price = float(quote.get("Global Quote", {}).get("05. price", 0))

        data["Name"] = data.get("Name") or ov.get("Name", ticker)
        data["PE Ratio"] = data.get("PE Ratio") or float(ov.get("PERatio", 0))
        data["PB Ratio"] = data.get("PB Ratio") or float(ov.get("PriceToBookRatio", 0))
        data["ROE"] = data.get("ROE") or float(ov.get("ReturnOnEquityTTM", 0))
        data["Debt/Equity"] = data.get("Debt/Equity") or float(ov.get("DebtEquityRatio", 0))
        data["EPS Growth"] = data.get("EPS Growth") or float(ov.get("QuarterlyEarningsGrowthYOY", 0))
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
# --- Scoring Logic ---
st.subheader("Raw Stock Data")
st.dataframe(df)

required_cols = ["PE Ratio", "PB Ratio", "ROE", "Debt/Equity", "EPS Growth"]
missing_cols = [col for col in required_cols if col not in df.columns]

if missing_cols:
    st.error(f"Missing columns in data: {', '.join(missing_cols)}")
    st.stop()

features = df[required_cols].copy()
features["PE Ratio"] = 1 / features["PE Ratio"]
features["PB Ratio"] = 1 / features["PB Ratio"]
features["Debt/Equity"] = 1 / features["Debt/Equity"]
features = features.fillna(features.mean())
normalized = MinMaxScaler().fit_transform(features)
df["Score"] = (normalized.mean(axis=1) * 100).round(2)

# --- Sector Penalty (Optional) ---
if avoid_sector_overload:
    sector_avg = df["Sector"].value_counts(normalize=True)
    sector_penalty = sector_avg * 0.2
    df["Score"] = df.apply(lambda r: r["Score"] * (1 - sector_penalty.get(r["Sector"], 0)), axis=1)

# --- Buy Signal Filter ---
buy_df = df[df["Score"] >= 40].copy()
buy_df = buy_df.sort_values("Score", ascending=False)
total_score = buy_df["Score"].sum()

buy_df["Allocation %"] = buy_df["Score"] / total_score
buy_df["Investment ($)"] = (buy_df["Allocation %"] * investment_amount).round(2)
buy_df["Est. Shares"] = (buy_df["Investment ($)"] / buy_df["Price"]).fillna(0).astype(int)

# --- Buy Signals ---
st.subheader("Buy Signals")
if not buy_df.empty:
    st.dataframe(buy_df[["Ticker", "Name", "Score", "Price", "Investment ($)", "Est. Shares", "Sector", "Source"]])
    st.download_button("Download Buy Signals", data=buy_df.to_csv(index=False), file_name="buy_signals.csv", mime="text/csv")
else:
    st.warning("No qualifying stocks at this time.")

# --- Watchlist (Optional) ---
if show_watchlist:
    st.subheader("Watchlist / Manual Compare")
    watchlist = df[df["Score"] < 40]
    st.dataframe(watchlist[["Ticker", "Name", "Score", "PE Ratio", "PB Ratio", "ROE", "Debt/Equity", "EPS Growth", "Sector"]])

# --- Sector Chart ---
st.subheader("Sector Diversification")
if not buy_df.empty:
    st.bar_chart(buy_df["Sector"].value_counts())
    # --- Backtest Chart ---
st.subheader("Backtest: Price History")
range_choice = st.selectbox("Select Backtest Range", ["1y", "3y", "5y"], index=2)

@st.cache_data
def get_price_history(ticker, period):
    try:
        df = yf.download(ticker, period=period)["Adj Close"]
        return df if not df.empty else None
    except:
        return None

price_data = {}
for t in buy_df["Ticker"]:
    history = get_price_history(t, period=range_choice)
    if history is not None:
        price_data[t] = history

if price_data:
    st.line_chart(pd.DataFrame(price_data))
else:
    st.warning("No historical price data available. Check internet access or try again later.")

# --- Rebalance Tool ---
st.subheader("Rebalance Plan")
current_shares = {}
for ticker in buy_df["Ticker"]:
    current_shares[ticker] = st.number_input(f"{ticker} - Current Shares", min_value=0, step=1, key=f"cur_{ticker}")

buy_df["Current Shares"] = buy_df["Ticker"].map(current_shares)
buy_df["Target Shares"] = buy_df["Est. Shares"]

def decide_action(cur, target):
    if cur < target:
        return f"BUY {target - cur}"
    elif cur > target:
        return f"SELL {cur - target}"
    return "HOLD"

buy_df["Action"] = buy_df.apply(lambda row: decide_action(row["Current Shares"], row["Target Shares"]), axis=1)
st.dataframe(buy_df[["Ticker", "Name", "Current Shares", "Target Shares", "Action"]])
rebalance_csv = buy_df[["Ticker", "Name", "Current Shares", "Target Shares", "Action"]].to_csv(index=False)
st.download_button("Download Rebalance Plan", data=rebalance_csv, file_name="rebalance_plan.csv", mime="text/csv")

# --- Wealth Projection ---
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

# --- News Display (Cleaned) ---
st.subheader("Latest News by Stock")
for _, row in buy_df.iterrows():
    with st.expander(f"{row['Ticker']} News"):
        articles = row.get("News", [])
        if isinstance(articles, list) and articles:
            for article in articles:
                title = article.get("title")
                url = article.get("url")
                if title and url:
                    st.markdown(f"- [{title}]({url})")
        else:
            st.write("No recent news available.")