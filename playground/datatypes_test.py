from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
db = client["iotsensing"]
collection = db["phq9"]

doc = collection.find_one()
for k, v in doc.items():
    print(f"{k}: {type(v)}")
