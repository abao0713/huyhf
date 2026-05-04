import log_config
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from trading_system.core.database import init_db, SessionLocal
from log_config import logger
import time

app = FastAPI(title="Trading API", description="交易系统API", version="1.0.0")


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
            "detail": str(exc)
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(f"HTTP exception: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP Error",
            "message": exc.detail
        }
    )


@app.on_event("startup")
def on_startup():
    logger.info("Starting up Trading API")
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise


@app.get("/")
def root():
    logger.debug("Root endpoint accessed")
    return {"message": "Trading API is running", "docs": "/docs"}


@app.get("/health")
def health_check():
    from sqlalchemy import text
    
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        logger.info("Health check: Database connected")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"Health check: Database connection failed - {str(e)}")
        raise HTTPException(status_code=503, detail={"status": "unhealthy", "database": "disconnected", "error": str(e)})

