import streamlit as st
from pymongo import MongoClient
import pandas as pd

client = MongoClient("mongodb://mongodb:27017")
db = client["test"]
collection = db["metrics"]

df = pd.DataFrame(collection.find())
df["date"] = pd.to_datetime(df["date"], format="%d.%m.%Y")
selected_user = st.session_state.get("user_id", None)

st.title("Metrics")
if selected_user:
    user_df = df[df["user_id"] == selected_user]
    st.dataframe(user_df.drop(columns=["_id"]))
else:
    st.warning("Please select a user in the Home tab.")
