from fastapi import APIRouter
from adapters.outbound.MongoPersistenceAdapter import MongoPersistenceAdapter

router = APIRouter()

# instantiate Mongo adapter
persistence = MongoPersistenceAdapter()

@router.get("/users")
def list_users():
    # Query distinct user IDs from any populated collection
    user_ids = persistence.collection_contextual_metrics.distinct("user_id")

    # If no contextual metrics exist, try analyzed_metrics
    if not user_ids:
        user_ids = persistence.collection_analyzed_metrics.distinct("user_id")

    # Convert to API format
    return [{"user_id": int(uid)} for uid in user_ids]
