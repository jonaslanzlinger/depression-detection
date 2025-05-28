import streamlit as st
from pymongo import MongoClient
import pandas as pd

from utils.refresh_procedure import refresh_procedure

st.title("DSM-5 Indicators")

client = MongoClient("mongodb://mongodb:27017")
db = client["iotsensing"]
collection = db["indicator_scores"]

if collection.count_documents({}) == 0:
    st.warning("No data available.")
    st.stop()


@st.cache_data
def load_users():
    df = pd.DataFrame(collection.find())
    return df["user_id"].unique()


st.sidebar.title("Actions")

if st.sidebar.button("🔄 Refresh Analysis"):
    refresh_procedure()

st.sidebar.subheader("Select User")
selected_user = st.sidebar.selectbox("User", load_users(), key="user_id")

df = pd.DataFrame(collection.find())
df["timestamp"] = pd.to_datetime(df["timestamp"])

selected_user = st.session_state.get("user_id", None)

if selected_user:
    user_df = df[df["user_id"] == selected_user]

    if user_df.empty:
        st.info("No DSM-5 indicator scores available for this user.")
        st.stop()

    pivot_df = user_df.pivot(index="timestamp", columns="indicator", values="score")
    indicators = sorted(pivot_df.columns.tolist())

    selected_indicators = st.multiselect(
        "",
        options=indicators,
        default=indicators,
    )

    if selected_indicators:
        st.line_chart(pivot_df[selected_indicators])
        filtered_table = user_df[user_df["indicator"].isin(selected_indicators)]
        st.dataframe(filtered_table.drop(columns=["_id"]))
    else:
        st.info("Please select at least one indicator to display.")
else:
    st.warning("Please select a user in the Home tab.")
