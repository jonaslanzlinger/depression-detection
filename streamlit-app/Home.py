import streamlit as st
from pymongo import MongoClient
import pandas as pd

client = MongoClient("mongodb://mongodb:27017")
db = client["test"]
collection = db["metrics"]

st.title("IoT Sensing – Dashboard")


@st.cache_data
def load_users():
    df = pd.DataFrame(collection.find())
    return df["user_id"].unique()


st.session_state["user_id"] = st.selectbox("Select User", load_users())
