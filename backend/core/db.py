"""MongoDB client + shared document utilities."""
import os
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Annotated, Any
from bson import ObjectId
from pydantic import BeforeValidator, BaseModel, Field, ConfigDict


def _validate_object_id(v: Any) -> str:
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, str):
        return v
    raise ValueError("Invalid ObjectId")


PyObjectId = Annotated[str, BeforeValidator(_validate_object_id)]


class BaseDocument(BaseModel):
    """Base for Mongo-backed documents. Maps _id -> id."""
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True, extra="ignore")

    id: PyObjectId | None = Field(default=None, alias="_id")

    @classmethod
    def from_mongo(cls, doc: dict | None):
        if doc is None:
            return None
        return cls.model_validate(doc)

    def to_mongo(self) -> dict:
        data = self.model_dump(by_alias=True, exclude_none=True)
        return data


_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return _client


def get_db():
    return get_client()[os.environ["DB_NAME"]]
