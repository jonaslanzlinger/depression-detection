from fastapi import FastAPI, HTTPException
from ports.UserRepositoryPort import UserRepositoryPort
import logging


def create_user_management_service(repository: UserRepositoryPort) -> FastAPI:
    app = FastAPI()

    @app.get("/users")
    async def get_users():
        """Get all registered users."""
        try:
            users = repository.get_all_users()
            return {"users": users}
        except Exception as e:
            logging.error(f"Error getting users: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/users/{user_id}")
    async def delete_user(user_id: str):
        """Delete a user by ID."""
        try:
            success = repository.delete_user(user_id)
            if success:
                return {"status": "deleted", "user_id": user_id}
            else:
                raise HTTPException(status_code=404, detail="User not found")
        except Exception as e:
            logging.error(f"Error deleting user: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    return app
