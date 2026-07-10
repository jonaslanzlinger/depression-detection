from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Union, Optional
from datetime import datetime
import logging
import traceback
import uuid

from ports.PersistencePort import PersistencePort
from core.models.Environment import Environment


class CreateEnvironmentRequest(BaseModel):
    # live/demo users are strings ("bruno", UUIDs); dataset users are ints. The old
    # `int` annotation made pydantic reject every live user at the door.
    user_id: Union[int, str]
    name: str
    description: Optional[str] = None


class UpdateEnvironmentRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


def create_service_environments(persistence: PersistencePort):
    router = APIRouter(prefix="/environments", tags=["environments"])

    @router.get("/")
    async def list_environments(user_id: Union[int, str] = Query(...)):
        try:
            environments = persistence.get_environments_by_user(user_id)
            return [e.to_dict() for e in environments]
        except Exception as e:
            logging.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/{environment_id}")
    async def get_environment(environment_id: str):
        try:
            environment = persistence.get_environment_by_id(environment_id)
            if not environment:
                raise HTTPException(status_code=404, detail="Environment not found")
            return environment.to_dict()
        except HTTPException:
            raise
        except Exception as e:
            logging.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/")
    async def create_environment(request: CreateEnvironmentRequest):
        try:
            environment = Environment(
                environment_id=str(uuid.uuid4()),
                user_id=request.user_id,
                name=request.name,
                description=request.description,
                created_at=datetime.utcnow(),
            )
            environment_id = persistence.save_environment(environment)
            return {"environment_id": environment_id}
        except Exception as e:
            logging.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))

    @router.put("/{environment_id}")
    async def update_environment(environment_id: str, request: UpdateEnvironmentRequest):
        try:
            environment = persistence.get_environment_by_id(environment_id)
            if not environment:
                raise HTTPException(status_code=404, detail="Environment not found")

            if request.name is not None:
                environment.name = request.name
            if request.description is not None:
                environment.description = request.description

            persistence.update_environment(environment)
            return {"status": "updated", "environment_id": environment_id}
        except HTTPException:
            raise
        except Exception as e:
            logging.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))

    @router.delete("/{environment_id}")
    async def delete_environment(environment_id: str):
        try:
            success = persistence.delete_environment(environment_id)
            if not success:
                raise HTTPException(status_code=404, detail="Environment not found")
            return {"status": "deleted", "environment_id": environment_id}
        except HTTPException:
            raise
        except Exception as e:
            logging.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))

    return router
