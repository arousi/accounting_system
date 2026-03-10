from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, scoped_session, sessionmaker


class Base(DeclarativeBase):
    pass


engine = None
SessionLocal = scoped_session(
    sessionmaker(autoflush=False, autocommit=False, expire_on_commit=False)
)


def init_database(app):
    global engine

    connect_args = {}
    if app.config["DATABASE_URL"].startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(app.config["DATABASE_URL"], future=True, connect_args=connect_args)
    SessionLocal.configure(bind=engine)

    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def remove_session(_exception=None):
    SessionLocal.remove()
