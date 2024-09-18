import uuid
from datetime import datetime, timedelta, timezone
from typing import Generator

import pytest
from pydantic import UUID4
from sqlalchemy import  create_engine, exc
from sqlalchemy.orm import DeclarativeBase, sessionmaker 

from fastapi_users_db_sqlalchemy_pelicanq import SQLAlchemyBaseUserTableUUID
from fastapi_users_db_sqlalchemy_pelicanq.access_token import (
    SQLAlchemyAccessTokenDatabase,
    SQLAlchemyBaseAccessTokenTableUUID,
)
from tests.conftest import DATABASE_URL


class Base(DeclarativeBase):
    pass


class AccessToken(SQLAlchemyBaseAccessTokenTableUUID, Base):
    pass


class User(SQLAlchemyBaseUserTableUUID, Base):
    pass


@pytest.fixture
def user_id() -> UUID4:
    return uuid.uuid4()


@pytest.fixture
def sqlalchemy_access_token_db(
    user_id: UUID4,
) -> Generator[SQLAlchemyAccessTokenDatabase[AccessToken], None, None]:
    engine = create_engine(DATABASE_URL)
    session_factory = sessionmaker(engine)

    Base.metadata.create_all(bind=engine)

    with session_factory() as session:
        user = User(
            id=user_id, email="lancelot@camelot.bt", hashed_password="guinevere"
        )
        session.add(user)
        session.commit()

        yield SQLAlchemyAccessTokenDatabase(session, AccessToken)

    Base.metadata.drop_all(bind=engine)


def test_queries(
    sqlalchemy_access_token_db: SQLAlchemyAccessTokenDatabase[AccessToken],
    user_id: UUID4,
):
    access_token_create = {"token": "TOKEN", "user_id": user_id}

    # Create
    access_token = sqlalchemy_access_token_db.create(access_token_create)
    assert access_token.token == "TOKEN"
    assert access_token.user_id == user_id

    # Update
    update_dict = {"created_at": datetime.now(timezone.utc)}
    updated_access_token = sqlalchemy_access_token_db.update(
        access_token, update_dict
    )
    assert updated_access_token.created_at.replace(microsecond=0) == update_dict[
        "created_at"
    ].replace(microsecond=0)

    # Get by token
    access_token_by_token = sqlalchemy_access_token_db.get_by_token(
        access_token.token
    )
    assert access_token_by_token is not None

    # Get by token expired
    access_token_by_token =  sqlalchemy_access_token_db.get_by_token(
        access_token.token, max_age=datetime.now(timezone.utc) + timedelta(hours=1)
    )
    assert access_token_by_token is None

    # Get by token not expired
    access_token_by_token =  sqlalchemy_access_token_db.get_by_token(
        access_token.token, max_age=datetime.now(timezone.utc) - timedelta(hours=1)
    )
    assert access_token_by_token is not None

    # Get by token unknown
    access_token_by_token =  sqlalchemy_access_token_db.get_by_token(
        "NOT_EXISTING_TOKEN"
    )
    assert access_token_by_token is None

    # Delete token
    sqlalchemy_access_token_db.delete(access_token)
    deleted_access_token = sqlalchemy_access_token_db.get_by_token(
        access_token.token
    )
    assert deleted_access_token is None


def test_insert_existing_token(
    sqlalchemy_access_token_db: SQLAlchemyAccessTokenDatabase[AccessToken],
    user_id: UUID4,
):
    access_token_create = {"token": "TOKEN", "user_id": user_id}
    sqlalchemy_access_token_db.create(access_token_create)

    with pytest.raises(exc.IntegrityError):
        sqlalchemy_access_token_db.create(access_token_create)
