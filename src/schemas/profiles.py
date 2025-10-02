from datetime import date
from typing import Optional

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl, ConfigDict
from src.database.models.accounts import GenderEnum

from src.validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)

class ProfileBaseSchema(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    gender: Optional[GenderEnum] = None
    date_of_birth: Optional[date] = None
    info: Optional[str] = None
    
class ProfileRequestSchema(ProfileBaseSchema):
    avatar: Optional[UploadFile] = File(None)
    
    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, value):
        if value:
            validate_name(value)
        return value
    
    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, value):
        if value:
            validate_name(value)
        return value
    
    
    @field_validator("avatar")
    @classmethod
    def validate_image(cls, value):
        if value:
            validate_image(value)
        return value
    
    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value):
        if value:
            validate_gender(value)
        return value
    
    @field_validator("date_of_birth")
    @classmethod
    def validate_birth_date(cls, value):
        if value:
            validate_birth_date(value)
        return value
    
    

class ProfileResponseSchema(ProfileBaseSchema):
    id: int
    user_id: int
    avatar: Optional[str] = None
    
    model_config: ConfigDict = ConfigDict(from_attributes=True)