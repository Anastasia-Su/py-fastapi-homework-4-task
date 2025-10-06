import os
import aioboto3
from datetime import datetime, timezone
from typing import cast
from fastapi.responses import HTMLResponse

from fastapi import APIRouter, Depends, status, HTTPException, BackgroundTasks
from sqlalchemy import select, delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.config import (
    get_jwt_auth_manager,
    get_settings,
    BaseAppSettings,
    get_accounts_email_notificator,
)

from src.database import (
    get_db,
    UserModel,
    UserGroupModel,
    UserGroupEnum,
    ActivationTokenModel,
    PasswordResetTokenModel,
    RefreshTokenModel,
    UserProfileModel,
)
from src.exceptions import BaseSecurityError, S3FileUploadError
from src.notifications import EmailSenderInterface
from src.schemas import ProfileRequestSchema, ProfileResponseSchema, ProfileBaseSchema
from src.security.interfaces import JWTAuthManagerInterface

from src.storages import S3StorageInterface, S3StorageClient
from src.config import get_s3_storage_client

from .utils import get_current_user, get_avatar_presigned_url


from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Depends
from typing import Optional
from datetime import date

from src.database.models.accounts import GenderEnum


from src.validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
)


router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    summary="User Profile Creation",
    description="Create user profile.",
    status_code=status.HTTP_201_CREATED,
)
async def create_profile(
    
    user_id: int,
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    gender: Optional[str] = Form(None),
    date_of_birth: Optional[date] = Form(None),
    info: Optional[str] = Form(None),
    avatar: Optional[UploadFile] = File(None),
    # user_data: ProfileRequestSchema = Depends(ProfileBaseSchema),
    db: AsyncSession = Depends(get_db),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
    current_user_id: UserModel = Depends(get_current_user),
    settings: BaseAppSettings = Depends(get_settings),
    
):
   
    # if current_user is None:
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="User not found or not active.",
    #     )
    try:
        if first_name:
            validate_name(first_name)
        if last_name:
            validate_name(last_name)
        if gender:
            validate_gender(gender)
        if date_of_birth:
            validate_birth_date(date_of_birth)
            
        if not info.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        
        if avatar:
            validate_image(avatar)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
        
    stmt_current = select(UserModel).options(joinedload(UserModel.group)).where(UserModel.id == current_user_id)
    result_current = await db.execute(stmt_current)
    authenticated_user = result_current.scalars().first()
    
    stmt_target = select(UserModel).options(joinedload(UserModel.group)).where(UserModel.id == user_id)
    result_target = await db.execute(stmt_target)
    target_user = result_target.scalars().first()
    
    # print("Found user:", current_user)
    # if current_user:
    #     print("User active?", current_user.is_active)


    if target_user is None or not target_user.is_active:
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )
    
    
    # Permission check
    if authenticated_user.id != user_id and authenticated_user.group.name != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    # Get user
    # stmt_user = (
    #     select(UserModel)
    #     .options(joinedload(UserModel.group))
    #     .where(UserModel.id == user_id)
    # )
    # result = await db.execute(stmt_user)
    # existing_user = result.scalars().first()
    

    # Check if profile exists
    stmt_profile = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    result = await db.execute(stmt_profile)
    existing_profile = result.scalars().first()
    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a profile.",
        )

    # Upload avatar if present
    avatar_url = None

    if avatar:
        try:
            # session = aioboto3.Session(
            #     aws_access_key_id="minioadmin", aws_secret_access_key="minioadmin"
            # # )

            # async with session.client(
            #     "s3",
            #     endpoint_url=f"http://{settings.S3_STORAGE_HOST}:{settings.S3_STORAGE_PORT}",
            # ) as s3:
            #     existing_buckets = await s3.list_buckets()
            #     if not any(
            #         b["Name"] == settings.S3_BUCKET_NAME
            #         for b in existing_buckets.get("Buckets", [])
            #     ):
            #         await s3.create_bucket(Bucket=settings.S3_BUCKET_NAME)

            file_bytes = await avatar.read()
            filename = f"avatars/{user_id}_avatar.jpg"
            await s3_client.upload_file(filename, file_bytes)
            # await s3.put_object(Bucket=settings.S3_BUCKET_NAME, Key=filename, Body=file_bytes)

    
            # avatar_url = f"http://{settings.S3_STORAGE_HOST}:{settings.S3_STORAGE_PORT}/{settings.S3_BUCKET_NAME}/{filename}"
            avatar_url = await get_avatar_presigned_url(filename)
            
            # validate_image(avatar)
        except S3FileUploadError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                # detail=str(e),
                detail="Failed to upload avatar. Please try again later.",
            )
        
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload avatar. Please try again later.",
                # detail=str(e),
            )

    # Create profile
    try:
        new_profile = UserProfileModel(
            user_id=user_id,
            first_name=first_name.lower(),
            last_name=last_name.lower(),
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=filename,
        )
        #await new_profile.model_validate_async()
        # await new_profile.model_validate_async()
        db.add(new_profile)
        await db.commit()
        await db.refresh(new_profile)
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            # detail="An error occurred during profile creation.",
            detail=str(e),
        ) from e

    return ProfileResponseSchema.model_validate(new_profile)


# async def create_profile(
#     user_id: int,
#     user_data: ProfileRequestSchema,
#     db: AsyncSession = Depends(get_db),
#     s3_client: S3StorageInterface = Depends(get_s3_storage_client),
#     current_user: UserModel = Depends(get_current_user),
# ) -> ProfileResponseSchema:

#     if current_user.id != user_id and current_user.group.name != "ADMIN":
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="You don't have permission to edit this profile.",
#         )

#     stmt_user = select(UserModel).options(joinedload(UserModel.group)).where(UserModel.id == user_id)
#     result = await db.execute(stmt_user)
#     existing_user = result.scalars().first()

#     if not existing_user or not existing_user.is_active:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="User not found or not active."
#         )


#     stmt_profile = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
#     result = await db.execute(stmt_profile)
#     existing_profile = result.scalars().first()
#     if existing_profile:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="User already has a profile."
#         )

#     avatar_url = None
#     if user_data.avatar:
#         try:
#             contents = await user_data.avatar.read()
#             avatar_url = await s3_client.upload_file(
#                 file_content=contents,
#                 bucket="avatars",
#                 key=f"{user_id}_avatar.jpg",
#             )
#         except Exception:
#             raise HTTPException(
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#                 detail="Failed to upload avatar. Please try again later."
#             )


#     try:
#         new_profile = UserProfileModel(
#             user_id=user_id,
#             first_name=user_data.first_name,
#             last_name=user_data.last_name,
#             gender=user_data.gender,
#             date_of_birth=user_data.date_of_birth,
#             info=user_data.info,
#             avatar=avatar_url,
#         )
#         db.add(new_profile)
#         print("DEBUG:", new_profile.first_name, new_profile.last_name, new_profile.gender, new_profile.date_of_birth, new_profile.info)

#         await db.commit()
#         await db.refresh(new_profile)
#     except SQLAlchemyError as e:
#         await db.rollback()
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="An error occurred during profile creation.",
#         ) from e
#     else:

#         return ProfileResponseSchema.model_validate(new_profile)
