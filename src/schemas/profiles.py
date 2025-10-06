from datetime import date
from typing import Optional

from fastapi import UploadFile, Form, File
from pydantic import BaseModel, field_validator, field_serializer, ConfigDict
from src.database.models.accounts import GenderEnum
from src.config import get_settings


settings = get_settings()


class ProfileBaseSchema(BaseModel):
    first_name: Optional[str] = Form(None)
    last_name: Optional[str] = Form(None)
    gender: Optional[GenderEnum] = Form(None)
    date_of_birth: Optional[date] = Form(None)
    info: Optional[str] = Form(None)


class ProfileResponseSchema(ProfileBaseSchema):
    id: int
    user_id: int
    avatar: Optional[str] = None

    model_config: ConfigDict = ConfigDict(from_attributes=True)

    @field_serializer("avatar")
    def serialize_avatar(self, avatar: str, _info):
        if not avatar:
            return None
        return f"http://{settings.S3_STORAGE_HOST}:{settings.S3_STORAGE_PORT}/{settings.S3_BUCKET_NAME}/{avatar}"
