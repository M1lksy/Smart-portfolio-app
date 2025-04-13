import streamlit as st
import pandas as pd
import requests
from sklearn.preprocessing import MinMaxScaler

st.title("Smart Portfolio: Value & Growth Picker")

investment_amount = st.number_input("Investment Amount ($)", value=500, step=100)

tickers = ["AAPL", "MSFT", "GOOGL", "TSLA"]
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

