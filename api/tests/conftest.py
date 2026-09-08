from __future__ import annotations

import os

import pytest

# Point the app at an isolated test database BEFORE importing app modules.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://ytauto:ytauto@localhost:5433/ytauto_test",
)
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-000000000000000000000000")
os.environ.setdefault("ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-pass")
os.environ.setdefault("STORAGE_LOCAL_ROOT", "/tmp/ytauto-test-storage")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import sqlalchemy as sa  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.models import Base  # noqa: E402


def _ensure_database() -> None:
    url = sa.make_url(settings.database_url)
    admin_url = url.set(database="postgres")
    engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        exists = conn.execute(
            sa.text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": url.database}
        ).scalar()
        if not exists:
            conn.execute(sa.text(f'CREATE DATABASE "{url.database}"'))
    engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _schema():
    _ensure_database()
    engine = sa.create_engine(settings.database_url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    engine.dispose()


@pytest.fixture()
def db():
    engine = sa.create_engine(settings.database_url)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSession()
    # clean slate per test
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db):
    from app.api.deps import get_db
    from app.main import create_app

    app = create_app()

    def _override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def admin_token(db):
    from app.core.security import hash_password
    from app.models.user import User

    user = User(
        email=settings.admin_email.lower(),
        password_hash=hash_password(settings.admin_password),
    )
    db.add(user)
    db.commit()
    from app.core.security import create_access_token

    return create_access_token(str(user.id))


@pytest.fixture()
def auth(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}
