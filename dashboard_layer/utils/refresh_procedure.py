import streamlit as st
import requests


def refresh_procedure():
    user_id = st.session_state["user_id"]

    AGGREGATE_METRICS_URL = (
        "http://temporal_context_modeling_layer:8082/aggregate_metrics"
    )

    CONTEXTUALIZE_METRICS_URL = (
        "http://temporal_context_modeling_layer:8082/compute_contextual_metrics"
    )

    ANALYZE_METRICS_URL = "http://analysis_layer:8083/analyze_metrics"

    DERIVE_INDICATOR_SCORES_URL = "http://analysis_layer:8083/derive_indicator_scores"

    try:
        res = requests.get(AGGREGATE_METRICS_URL, params={"user_id": user_id})
        res.raise_for_status()
        st.success("Metrics aggregated.")

        res = requests.get(CONTEXTUALIZE_METRICS_URL, params={"user_id": user_id})
        res.raise_for_status()
        st.success("Metrics contextualized.")

        # res = requests.get(ANALYZE_METRICS_URL, params={"user_id": user_id})
        # res.raise_for_status()
        # st.success("Metrics analyzed.")

        # res = requests.get(DERIVE_INDICATOR_SCORES_URL, params={"user_id": user_id})
        # res.raise_for_status()
        # st.success("Indicator scores derived.")

    except Exception as e:
        st.error(f"Failed to refresh analysis: {e}")
