import streamlit as st
from pymongo import MongoClient
import pandas as pd

st.title("IoT Sensing – Dashboard")

client = MongoClient("mongodb://mongodb:27017")
db = client["iotsensing"]
collection = db["metrics"]

if collection.count_documents({}) == 0:
    st.warning("No data available.")
    st.stop()


@st.cache_data
def load_users():
    df = pd.DataFrame(collection.find())
    return df["user_id"].unique()


st.session_state["user_id"] = st.selectbox("Select User", load_users())

col1, col2 = st.columns(2)

with col1:
    if st.button("Reset User"):
        result = collection.delete_many({"user_id": st.session_state["user_id"]})
        st.success(
            f"Deleted {result.deleted_count} records for user {st.session_state['user_id']}"
        )
        st.rerun()

with col2:
    if st.button("Reset All"):
        result = collection.delete_many({})
        st.success(f"Deleted all records ({result.deleted_count} total)")
        st.rerun()
