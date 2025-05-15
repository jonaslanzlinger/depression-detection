import streamlit as st
from pymongo import MongoClient
import pandas as pd

st.title("DSM-5 Indicators")

client = MongoClient("mongodb://mongodb:27017")
db = client["iotsensing"]
collection = db["metrics"]

if collection.count_documents({}) == 0:
    st.warning("Please select a user in the Home tab.")
    st.stop()

df = pd.DataFrame(collection.find())
df["timestamp"] = pd.to_datetime(df["timestamp"])
selected_user = st.session_state.get("user_id", None)

if selected_user:
    user_df = df[df["user_id"] == selected_user]
    st.dataframe(user_df.drop(columns=["_id"]))
else:
    st.warning("Please select a user in the Home tab.")
