import streamlit as st
from pymongo import MongoClient
import pandas as pd

st.title("Metrics")

client = MongoClient("mongodb://mongodb:27017")
db = client["iotsensing"]

collections = {
    "Raw Metrics": "metrics",
    "Aggregated Metrics": "aggregated_daily_metrics",
    "Contextual Metrics": "contextual_daily_metrics",
}


@st.cache_data
def load_users():
    df = pd.DataFrame(collection.find())
    return df["user_id"].unique()


st.sidebar.title("Actions")

if st.sidebar.button("🔄 Refresh Analysis"):
    pass

st.sidebar.subheader("Select User")
selected_user = st.sidebar.selectbox("User", load_users(), key="user_id")

st.markdown(
    "This view shows the collected metrics through three different stages of the analysis process.  \n"
    "**Raw metrics:** Collected directly from the sensors.  \n"
    "**Aggregated metrics:** Daily averages computed per metric.  \n"
    "**Contextual metrics:** Daily averages in temporal context per metric. or processed metrics that consider baseline and variability."
)

selected_view = st.radio("", list(collections.keys()), horizontal=True)

collection_name = collections[selected_view]
collection = db[collection_name]
docs = list(collection.find({"user_id": selected_user}))

st.header(selected_view)

if not docs:
    st.info(f"No {selected_view.lower()} found for this user.")
else:
    df = pd.DataFrame(docs)

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        if collection_name == "contextual_daily_metrics":
            chart_data = df.pivot_table(
                index="timestamp",
                columns="metric_name",
                values="metric_contextual_value",
            )
        else:
            chart_data = df.pivot_table(
                index="timestamp",
                columns="metric_name",
                values="metric_value",
            )
        st.line_chart(chart_data)

    st.dataframe(df.drop(columns=["_id"]))
