from sqlalchemy import event
from sqlmodel import SQLModel, Session, create_engine

from .config import settings

engine = create_engine(
    f"sqlite:///{settings.db_path}",
    connect_args={"check_same_thread": False, "timeout": 60},
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_connection, connection_record) -> None:  # noqa: ARG001
    """WAL + busy timeout so concurrent ingests / detection imports contend less."""
    cur = dbapi_connection.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute("PRAGMA busy_timeout=60000")
    cur.close()


def init_db() -> None:
    from .. import models  # noqa: F401  (register tables)
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
