import streamlit as st
from pymongo import MongoClient
import pandas as pd


st.title("PHQ-9 Questionnaire")

client = MongoClient("mongodb://mongodb:27017")
db = client["iotsensing"]
collection_metrics = db["metrics"]
collection_phq9 = db["phq9"]

if collection_metrics.count_documents({}) == 0:
    st.warning("Please select a user in the Home tab.")
    st.stop()

selected_user = st.session_state.get("user_id", None)

if selected_user:

    st.markdown(
        f"**Over the last 2 weeks, how often have you been bothered by any of the following problems?**"
    )

    phq9_questions = {
        "q1": "1. Little interest or pleasure in doing things",
        "q2": "2. Feeling down, depressed, or hopeless",
        "q3": "3. Trouble falling or staying asleep, or sleeping too much",
        "q4": "4. Feeling tired or having little energy",
        "q5": "5. Poor appetite or overeating",
        "q6": "6. Feeling bad about yourself – or that you are a failure or have let yourself or your family down",
        "q7": "7. Trouble concentrating on things, such as reading the newspaper or watching television",
        "q8": "8. Moving or speaking so slowly that other people could have noticed. Or the opposite – being so figety or restless that you have been moving around a lot more than usual",
        "q9": "9. Thoughts that you would be better off dead, or of hurting yourself",
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
    st.markdown(f"### Total Score: **{total_score}**")

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
            "timestamp": pd.Timestamp.utcnow(),
        }
        collection_phq9.insert_one(entry)
        st.success("PHQ-9 responses submitted successfully.")


else:
    st.warning("Please select a user in the Home tab.")
