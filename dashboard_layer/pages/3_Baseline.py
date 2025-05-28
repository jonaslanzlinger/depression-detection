import streamlit as st
from pymongo import MongoClient
import pandas as pd
from utils.refresh_procedure import refresh_procedure

st.title("Baseline")

client = MongoClient("mongodb://mongodb:27017")
db = client["iotsensing"]
collection = db["baseline"]

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

if selected_user:
    baseline_docs = list(collection.find({"user_id": selected_user}))
    if baseline_docs:
        baseline_df = pd.DataFrame(baseline_docs)
        baseline_df["date"] = pd.to_datetime(baseline_df["date"])

        baseline_pivot = baseline_df.pivot(
            index="date", columns="metric_name", values="mean"
        )

        st.subheader("Baseline Mean Values Over Time")

        all_metrics = sorted(baseline_pivot.columns.tolist())
        selected_metrics = st.multiselect(
            "Select metrics to display:",
            options=all_metrics,
            default=all_metrics[:5],
        )

        if selected_metrics:
            st.line_chart(baseline_pivot[selected_metrics])
        else:
            st.info("Please select at least one metric to display.")
    else:
        st.info("No baseline data available for this user.")
else:
    st.warning("Please select a user in the Home tab.")
    st.stop()
