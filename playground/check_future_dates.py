from pymongo import MongoClient
from datetime import datetime, timedelta

def check_future_dates():
    client = MongoClient("mongodb://mongodb:27017")
    db = client["iotsensing"]
    
    collections = ["raw_metrics", "aggregated_metrics", "contextual_metrics", "analyzed_metrics", "indicator_scores"]
    
    # Define "future" as anything after tomorrow
    future_threshold = datetime.utcnow() + timedelta(days=1)
    
    print(f"Checking for records after: {future_threshold}")
    
    for col_name in collections:
        count = db[col_name].count_documents({"timestamp": {"$gt": future_threshold}})
        if count > 0:
            print(f"Collection '{col_name}': {count} records in the future.")
            # Get sample
            sample = db[col_name].find_one({"timestamp": {"$gt": future_threshold}})
            print(f"  - Sample timestamp: {sample['timestamp']}")
        else:
            print(f"Collection '{col_name}': OK")

if __name__ == "__main__":
    check_future_dates()
