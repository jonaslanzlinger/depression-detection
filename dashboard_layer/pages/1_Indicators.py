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

    indicators_df = user_df[["timestamp", "indicator_scores"]].copy()
    indicators_df = pd.concat(
        [
            indicators_df.drop(columns=["indicator_scores"]),
            indicators_df["indicator_scores"].apply(pd.Series),
        ],
        axis=1,
    )

    indicators = sorted([col for col in indicators_df.columns if col != "timestamp"])

    selected_indicators = st.multiselect(
        "Select:",
        options=indicators,
        default=indicators,
    )

    if selected_indicators:
        st.line_chart(indicators_df.set_index("timestamp")[selected_indicators])
        st.dataframe(indicators_df[["timestamp"] + selected_indicators])
    else:
        st.info("Please select at least one indicator to display.")
else:
    st.warning("Please select a user in the Home tab.")
