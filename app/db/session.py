from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings

SessionFactory = sessionmaker[Session]


def build_engine(settings: Settings) -> Engine:
    connect_args = (
        {"check_same_thread": False} if settings.resolved_database_url.startswith("sqlite") else {}
    )
    return create_engine(settings.resolved_database_url, connect_args=connect_args)


def build_session_factory(engine: Engine) -> SessionFactory:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope(factory: SessionFactory) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
