# app/models/user.py

from fastapi_users.db import SQLAlchemyUserDatabase, SQLAlchemyBaseUserTableUUID
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.db.base import Base
from app.db.session import get_async_session


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User)
