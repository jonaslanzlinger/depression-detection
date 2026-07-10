from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import logging
import traceback
import uuid

from ports.PersistencePort import PersistencePort
from core.models.Board import Board


class CreateBoardRequest(BaseModel):
    user_id: int
    mac_address: str
    name: str
    environment_id: str


class UpdateBoardRequest(BaseModel):
    name: Optional[str] = None
    environment_id: Optional[str] = None
    is_active: Optional[bool] = None
    port: Optional[int] = None


def create_service_boards(persistence: PersistencePort):
    router = APIRouter(prefix="/boards", tags=["boards"])

    @router.get("/")
    async def list_boards(user_id: int = Query(...)):
        try:
            boards = persistence.get_boards_by_user(user_id)
            return [b.to_dict() for b in boards]
        except Exception as e:
            logging.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/{board_id}")
    async def get_board(board_id: str):
        try:
            board = persistence.get_board_by_id(board_id)
            if not board:
                raise HTTPException(status_code=404, detail="Board not found")
            return board.to_dict()
        except HTTPException:
            raise
        except Exception as e:
            logging.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/")
    async def create_board(request: CreateBoardRequest):
        try:
            board = Board(
                board_id=str(uuid.uuid4()),
                user_id=request.user_id,
                mac_address=request.mac_address,
                name=request.name,
                environment_id=request.environment_id,
                port=0,
                is_active=False,
                created_at=datetime.utcnow(),
            )
            board_id = persistence.save_board(board)
            return {"board_id": board_id}
        except Exception as e:
            logging.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))

    @router.put("/{board_id}")
    async def update_board(board_id: str, request: UpdateBoardRequest):
        try:
            board = persistence.get_board_by_id(board_id)
            if not board:
                raise HTTPException(status_code=404, detail="Board not found")

            if request.name is not None:
                board.name = request.name
            if request.environment_id is not None:
                board.environment_id = request.environment_id
            if request.is_active is not None:
                board.is_active = request.is_active
            if request.port is not None:
                board.port = request.port

            persistence.update_board(board)
            return {"status": "updated", "board_id": board_id}
        except HTTPException:
            raise
        except Exception as e:
            logging.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))

    @router.delete("/{board_id}")
    async def delete_board(board_id: str):
        try:
            success = persistence.delete_board(board_id)
            if not success:
                raise HTTPException(status_code=404, detail="Board not found")
            return {"status": "deleted", "board_id": board_id}
        except HTTPException:
            raise
        except Exception as e:
            logging.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))

    return router
