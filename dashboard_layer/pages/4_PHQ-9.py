import streamlit as st
from pymongo import MongoClient
import pandas as pd
import requests
from utils.refresh_procedure import refresh_procedure


st.title("PHQ-9 Questionnaire")

client = MongoClient("mongodb://mongodb:27017")
db = client["iotsensing"]
collection_metrics = db["raw_metrics"]
collection_phq9 = db["phq9"]

if collection_metrics.count_documents({}) == 0:
    st.warning("No data available.")
    st.stop()


@st.cache_data
def load_users():
    df = pd.DataFrame(collection_metrics.find())
    return df["user_id"].unique()


st.sidebar.title("Actions")

if st.sidebar.button("🔄 Refresh Analysis"):
    refresh_procedure()

st.sidebar.subheader("Select User")
selected_user = st.sidebar.selectbox("User", load_users(), key="user_id")

selected_user = st.session_state.get("user_id", None)

if selected_user:

    st.markdown(
        f"Over the last 2 weeks, how often have you been bothered by any of the following problems?"
    )

    phq9_questions = {
        "1_depressed_mood": "1. Little interest or pleasure in doing things",
        "2_loss_of_interest": "2. Feeling down, depressed, or hopeless",
        "3_significant_weight_changes": "3. Trouble falling or staying asleep, or sleeping too much",
        "4_insomnia_hypersomnia": "4. Feeling tired or having little energy",
        "5_psychomotor_retardation_agitation": "5. Poor appetite or overeating",
        "6_fatigue_loss_of_energy": "6. Feeling bad about yourself – or that you are a failure or have let yourself or your family down",
        "7_feelings_of_worthlessness_guilt": "7. Trouble concentrating on things, such as reading the newspaper or watching television",
        "8_diminished_ability_to_think_or_concentrate": "8. Moving or speaking so slowly that other people could have noticed. Or the opposite – being so figety or restless that you have been moving around a lot more than usual",
        "9_recurrent_thoughts_of_death_or_being_suicidal": "9. Thoughts that you would be better off dead, or of hurting yourself",
    }

    score_options = {
        "Not at all (0)": 0,
        "Several days (1)": 1,
        "More than half the days (2)": 2,
        "Nearly every day (3)": 3,
    }

    phq9_scores = {}

    for key, question in phq9_questions.items():
        label = st.selectbox(question, list(score_options.keys()), key=key)
        phq9_scores[key] = score_options[label]

    total_score = sum(phq9_scores.values())
    st.markdown("---")
    st.markdown(f"## Total Score: **{total_score}**")

    impact_labels = {
        "Not difficult at all": 0,
        "Somewhat difficult": 1,
        "Very difficult": 2,
        "Extremely difficult": 3,
    }
    impact_label = st.selectbox(
        "10. If you checked off any problems, how difficult have these problems made it for you to do your work, take care of things at home, or get along with other people?",
        list(impact_labels.keys()),
        key="q10",
    )
    functional_impact = {"label": impact_label, "score": impact_labels[impact_label]}

    if st.button("Submit"):
        entry = {
            "user_id": selected_user,
            "phq9_scores": phq9_scores,
            "total_score": total_score,
            "functional_impact": functional_impact,
            "timestamp": pd.Timestamp.utcnow().isoformat(),
        }

        try:
            response = requests.post(
                "http://analysis_layer:8083/finetune_baseline",
                json=entry,
            )
            if response.status_code == 200:
                st.success("PHQ-9 submitted. Baseline recomputed.")
            else:
                st.warning(f"Baseline finetuning failed: {response.status_code}")
        except Exception as e:
            st.error(f"Request failed: {e}")

        collection_phq9.insert_one(entry)


else:
    st.warning("Please select a user in the Home tab.")
