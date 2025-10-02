from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.security.interfaces import JWTAuthManagerInterface


from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from src.exceptions import BaseSecurityError
from src.config import get_jwt_auth_manager
from src.database import get_db, UserModel



bearer_scheme = HTTPBearer()



async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
):
    token = credentials.credentials  # Extract token from Bearer header

    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
    except BaseSecurityError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
            # detail="Authorization header is missing"
        )

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    stmt = select(UserModel).options(joinedload(UserModel.group)).where(UserModel.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or not active.",
        )

    return user






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
