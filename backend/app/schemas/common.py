# app/schemas/common.py
from pydantic import BaseModel


class DeleteResponse(BaseModel):
    deleted: bool = True
    id: int | str | None = None