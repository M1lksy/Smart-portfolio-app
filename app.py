import streamlit as st
import requests

st.title("API Test: AAPL Data")

api_key = "rrRi5vJI4MPAQIH2k00JkyAanMZTRQkv"
url = f"https://financialmodelingprep.com/api/v3/profile/AAPL?apikey={api_key}"

try:
    response = requests.get(url)
    data = response.json()

    if isinstance(data, list) and len(data) > 0:
        profile = data[0]
        name = profile.get("companyName", "N/A")
        price = profile.get("price", "N/A")

        st.success("Data fetched successfully!")
        st.write(f"**Company Name:** {name}")
        st.write(f"**Current Price:** ${price}")
    else:
        st.warning("API returned no usable data.")

except Exception as e:
    st.error(f"Failed to fetch AAPL data: {e}")
