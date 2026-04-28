"""Shared Pydantic response schemas for API consistency"""
from pydantic import BaseModel


class ActionResponse(BaseModel):
    success: bool
    message: str
