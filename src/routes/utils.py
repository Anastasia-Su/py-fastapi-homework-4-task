import aioboto3
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.security.interfaces import JWTAuthManagerInterface


from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from src.exceptions import BaseSecurityError, TokenExpiredError, InvalidTokenError
from src.config import get_jwt_auth_manager, get_settings, BaseAppSettings
from src.database import get_db, UserModel
from src.security import get_token



bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    # db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    
):
    # print("Raw credentials:", credentials)
    # if credentials:
    #     print("Scheme:", credentials.scheme)
    #     print("Token:", credentials.credentials)
        
    # if credentials is None:  
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="Authorization header is missing",
    #         #detail="Invalid Authorization header format. Expected 'Bearer <token>'",
    #     )
        
    # if credentials.scheme.lower() != "bearer":
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="Invalid Authorization header format. Expected 'Bearer <token>'",
    #     )
        
    # token = credentials.credentials  # Extract token from Bearer header
 
    token = get_token(request)
    try:
        payload = jwt_manager.decode_access_token(token)
        print("Decoded payload:", payload)
        user_id = payload.get("user_id")
        print("Looking up user_id:", user_id)
    except TokenExpiredError as e:  
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    except BaseSecurityError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
        
    return user_id

    stmt = select(UserModel).options(joinedload(UserModel.group)).where(UserModel.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()
    
    
    print("Found user:", user)
    if user:
        print("User active?", user.is_active)


    if user is None or not user.is_active:
        return None
        # raise HTTPException(
        #     status_code=status.HTTP_401_UNAUTHORIZED,
        #     detail="User not found or not active.",
        # )

    return user


async def get_avatar_presigned_url(file_name: str):
    settings: BaseAppSettings = get_settings()
    session = aioboto3.Session(
        aws_access_key_id=settings.S3_STORAGE_ACCESS_KEY,
        aws_secret_access_key=settings.S3_STORAGE_SECRET_KEY
    )
    async with session.client("s3", endpoint_url=f"http://{settings.S3_STORAGE_HOST}:{settings.S3_STORAGE_PORT}") as s3:
       
        url = await s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET_NAME, "Key": file_name},
            ExpiresIn=3600 
        )
        return url








# async def get_current_user(
#     request: Request,
#     db: AsyncSession = Depends(get_db),
#     jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
# ) -> UserModel:
#     """
#     Dependency to retrieve the currently authenticated user from the Authorization header.
#     """

#     auth_header = request.headers.get("Authorization")
#     if not auth_header:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Authorization header is missing",
#         )

#     if not auth_header.startswith("Bearer "):
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid Authorization header format. Expected 'Bearer <token>'",
#         )

#     token = auth_header.split(" ", 1)[1]

#     try:
#         payload = jwt_manager.decode_access_token(token)
#         user_id = payload.get("user_id")
#     except BaseSecurityError as error:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail=str(error),
#         )

#     if not user_id:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid token payload",
#         )

#     stmt = select(UserModel).where(UserModel.id == user_id)
#     result = await db.execute(stmt)
#     user = result.scalars().first()

#     if not user or not user.is_active:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="User not found or not active.",
#         )

#     return user
