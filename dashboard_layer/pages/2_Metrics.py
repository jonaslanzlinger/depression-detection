import streamlit as st
from pymongo import MongoClient
import pandas as pd
from utils.refresh_procedure import refresh_procedure

st.title("Metrics")

client = MongoClient("mongodb://mongodb:27017")
db = client["iotsensing"]
collection_raw_metrics = db["raw_metrics"]

collections = {
    "Raw Metrics": "raw_metrics",
    "Aggregated Metrics": "aggregated_metrics",
    "Contextual Metrics": "contextual_metrics",
    "Analyzed Metrics": "analyzed_metrics",
}


@st.cache_data
def load_users():
    df = pd.DataFrame(collection_raw_metrics.find())
    return df["user_id"].unique()


st.sidebar.title("Actions")

if st.sidebar.button("🔄 Refresh Analysis"):
    refresh_procedure()

st.sidebar.subheader("Select User")
selected_user = st.sidebar.selectbox("User", load_users(), key="user_id")

st.markdown(
    "This view shows the collected metrics through three different stages of the analysis process.  \n"
    "**Raw metrics:** Collected directly from the sensors.  \n"
    "**Aggregated metrics:** Daily averages computed per metric.  \n"
    "**Contextual metrics:** Daily averages in temporal context per metric. or processed metrics that consider baseline and variability."
)

selected_view = st.radio("Select:", list(collections.keys()), horizontal=True)

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

        if collection_name == "raw_metrics":
            chart_data = df.pivot_table(
                index="timestamp",
                columns="metric_name",
                values="metric_value",
            )
        if collection_name == "aggregated_metrics":
            chart_data = df.pivot_table(
                index="timestamp",
                columns="metric_name",
                values="aggregated_value",
            )
        if collection_name == "contextual_metrics":
            chart_data = df.pivot_table(
                index="timestamp",
                columns="metric_name",
                values="contextual_value",
            )
        if collection_name == "analyzed_metrics":
            chart_data = df.pivot_table(
                index="timestamp",
                columns="metric_name",
                values="analyzed_value",
            )

        available_metrics = list(chart_data.columns)
        selected_metrics = st.multiselect(
            "Select:",
            options=available_metrics,
            default=available_metrics,
        )

        filtered_chart_data = chart_data[selected_metrics]

        st.line_chart(filtered_chart_data)

        filtered_df = df[df["metric_name"].isin(selected_metrics)]

        st.dataframe(filtered_df.drop(columns=["_id"]))
