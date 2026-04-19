from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from trading_system.core.config import settings
from trading_system.models import Base
from log_config import logger

logger.info(f"Creating database engine with connection pool, URL: {settings.database_url}")
# 强制设置数据库URL为正确的值
DATABASE_URL = "mysql+pymysql://root:305634841@localhost:3306/trading_db"
logger.info(f"Forcing database URL to: {DATABASE_URL}")

engine = create_engine(
    DATABASE_URL,
    pool_size=settings.pool_size,
    max_overflow=settings.max_overflow,
    pool_timeout=settings.pool_timeout,
    pool_recycle=settings.pool_recycle,
    echo=settings.echo,
    pool_pre_ping=True
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    logger.debug("Database session created")
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {str(e)}")
        raise
    finally:
        logger.debug("Database session closed")
        db.close()


def init_db():
    logger.info("Initializing database tables")
    try:
        Base.metadata.create_all(bind=engine)
        logger.debug("Database tables created or already exist")
    except Exception as e:
        logger.error(f"Failed to create database tables: {str(e)}")
        raise
