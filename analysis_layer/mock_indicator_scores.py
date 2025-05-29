from pymongo import MongoClient
from datetime import datetime

# Connect to MongoDB
client = MongoClient("mongodb://localhost:27017")
db = client["iotsensing"]
collection = db["dsm5_indicator_scores"]

# Define today's date (timestamp will be 00:00:00)
timestamp = (
    datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
)

# Define mock predicted scores for user 1
mock_scores = {
    "1_depressed_mood": 1.5,
    "2_loss_of_interest": 2.0,
    "3_significant_weight_changes": 0.5,
    "4_insomnia_hypersomnia": 1.0,
    "5_psychomotor_retardation_agitation": 0.0,
    "6_fatigue_loss_of_energy": 0.5,
    "7_feelings_of_worthlessness_guilt": 2.5,
    "8_diminished_ability_to_think_or_concentrate": 1.2,
    "9_recurrent_thoughts_of_death_or_being_suicidal": 0.0,
}

# Create individual documents per indicator
docs = [
    {
        "user_id": 1,
        "indicator": indicator,
        "score": score,
        "timestamp": timestamp,
    }
    for indicator, score in mock_scores.items()
]

# Insert into MongoDB
result = collection.insert_many(docs)
print(f"Inserted {len(result.inserted_ids)} mock DSM-5 scores for user 1.")
