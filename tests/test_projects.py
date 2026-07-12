from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    with TestingSessionLocal() as session:
        yield session

    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_create_and_list_projects(client: TestClient) -> None:
    payload = {
        "name": "Demo API",
        "description": "Sample project for M1.",
        "base_url": "https://example.com",
    }

    create_response = client.post("/projects", json=payload)
    list_response = client.get("/projects")

    assert create_response.status_code == 201
    assert create_response.json()["name"] == "Demo API"
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["base_url"] == "https://example.com/"


def test_duplicate_project_name_returns_conflict(client: TestClient) -> None:
    payload = {"name": "Demo API"}

    first_response = client.post("/projects", json=payload)
    second_response = client.post("/projects", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409
