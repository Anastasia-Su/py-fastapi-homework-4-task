
import os
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
from src.exceptions import BaseSecurityError
from src.notifications import EmailSenderInterface
from src.schemas import ProfileRequestSchema, ProfileResponseSchema
from src.security.interfaces import JWTAuthManagerInterface

from src.storages import S3StorageInterface, S3StorageClient
from src.config import get_s3_storage_client

from .utils import get_current_user


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
# # from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Depends
# # from typing import Optional
# # from datetime import date
# # from sqlalchemy.ext.asyncio import AsyncSession
# # from sqlalchemy import select
# # from sqlalchemy.orm import joinedload
# # from sqlalchemy.exc import SQLAlchemyError

# # from src.database.models.accounts import UserModel, UserProfileModel, GenderEnum
# # from src.schemas.profiles import ProfileResponseSchema
# # from src.services.s3 import S3StorageInterface
# # from src.dependencies import get_db, get_s3_storage_client, get_current_user
# # from src.validation import validate_name, validate_image, validate_gender, validate_birth_date

# router = APIRouter()


# @router.post(
#     "/users/{user_id}/profile/",
#     response_model=ProfileResponseSchema,
#     summary="User Profile Creation",
#     description="Create user profile.",
#     status_code=status.HTTP_201_CREATED,
# )
async def create_profile(
    user_id: int,
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    gender: Optional[GenderEnum] = Form(None),
    date_of_birth: Optional[date] = Form(None),
    info: Optional[str] = Form(None),
    avatar: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client),
    current_user: UserModel = Depends(get_current_user),
    # user_data: ProfileRequestSchema = Depends(),
):
    # Permission check
    if current_user.id != user_id and current_user.group.name != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this profile.",
        )

    # Get user
    stmt_user = (
        select(UserModel)
        .options(joinedload(UserModel.group))
        .where(UserModel.id == user_id)
    )
    result = await db.execute(stmt_user)
    existing_user = result.scalars().first()
    if not existing_user or not existing_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

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
    UPLOAD_DIR = "static/avatars"
    if avatar:
        try:
            
            
            import aioboto3

            session = aioboto3.Session(
                aws_access_key_id="minioadmin",
                aws_secret_access_key="minioadmin"
            )

            async with session.client("s3", endpoint_url="http://localhost:9000") as s3:
                # Create bucket if it doesn't exist
                existing_buckets = await s3.list_buckets()
                if not any(b["Name"] == "theater-storage" for b in existing_buckets.get("Buckets", [])):
                    await s3.create_bucket(Bucket="theater-storage")
            
            
            async def get_avatar_presigned_url(file_name: str):
                import aioboto3

                session = aioboto3.Session(
                    aws_access_key_id="minioadmin",
                    aws_secret_access_key="minioadmin"
                )
                async with session.client("s3", endpoint_url="http://localhost:9000") as s3:
                    url = await s3.generate_presigned_url(
                        "get_object",
                        Params={"Bucket": "theater-storage", "Key": file_name},
                        ExpiresIn=3600  # URL valid for 1 hour
                    )
                    return url

            
            
            file_bytes = await avatar.read()
            filename = f"{user_id}_avatar.jpg"
            await s3_client.upload_file(filename, file_bytes)
            avatar_url = await get_avatar_presigned_url(filename)
            #Local
            # os.makedirs(UPLOAD_DIR, exist_ok=True)
            # file_path = os.path.join(UPLOAD_DIR, f"{user_id}_{avatar.filename}")
            # contents = await avatar.read()
            # with open(file_path, "wb") as f:
            #     f.write(contents)
            # avatar_url = file_path
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                # detail="Failed to upload avatar. Please try again later.",
                detail=str(e)
            )

    # Create profile
    try:
        new_profile = UserProfileModel(
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            info=info,
            avatar=avatar_url,
        )
        db.add(new_profile)
        await db.commit()
        await db.refresh(new_profile)
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during profile creation.",
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
