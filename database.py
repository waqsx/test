from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config import Config, absolute_path_dotenv

config = Config(_env_file=absolute_path_dotenv)
db_url = config.db_url

engine = create_engine(db_url) #, echo=True
Session = sessionmaker(bind=engine)


class Base(DeclarativeBase): pass


Base.metadata.create_all(bind=engine)


def get_db():
    db = Session()
    try:
        yield db
    finally:
        db.close()