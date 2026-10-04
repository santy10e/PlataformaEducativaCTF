import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.admin import router as admin_router
from app.auth import router as auth_router
from app.classes_api import router as classes_router
from app.config import settings
from app.ctf_api import router as ctf_router
from app.database import check_database
from app.maintenance import cleanup_once
from app.scoring_api import router as scoring_router
from app.teaching_api import router as teaching_router
from app.users_api import router as users_router

logger = logging.getLogger("cyberlab")
logging.basicConfig(level=settings.log_level, format='{"level":"%(levelname)s","message":"%(message)s"}')


async def maintenance_loop() -> None:
    while True:
        try:
            deleted_sessions, deleted_files = await asyncio.to_thread(cleanup_once)
            logger.info("Maintenance complete: sessions=%d temp_files=%d", deleted_sessions, deleted_files)
        except Exception:
            logger.exception("Maintenance job failed")
        await asyncio.sleep(6 * 60 * 60)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    task = asyncio.create_task(maintenance_loop())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="CYBERLAB API", version="0.1.0", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(users_router)
app.include_router(classes_router)
app.include_router(ctf_router)
app.include_router(scoring_router)
app.include_router(teaching_router)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
    codes = {401: "AUTHENTICATION_REQUIRED", 403: "ACCESS_DENIED", 404: "RESOURCE_NOT_FOUND", 409: "CONFLICT", 422: "VALIDATION_ERROR", 429: "RATE_LIMITED"}
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": codes.get(exc.status_code, "REQUEST_FAILED"), "message": str(exc.detail), "details": {}}}, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"error": {"code": "VALIDATION_ERROR", "message": "request validation failed", "details": {"issues": exc.errors()}}})


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    try:
        check_database()
    except Exception as exc:
        logger.exception("Database health check failed")
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ok"}
