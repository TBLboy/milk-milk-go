from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.master_data import router as master_data_router
from app.api.work_orders import router as work_orders_router
from app.api.evidence import router as evidence_router
from app.api.labels import router as labels_router
from app.api.operations import router as operations_router
from app.core.config import get_settings
from app.db.models import initialize_database


@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize_database()
    yield


settings = get_settings()
app = FastAPI(title="牧衡辅料称重防错系统", version=settings.app_version, lifespan=lifespan)
app.include_router(health_router, prefix=settings.api_prefix)
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(master_data_router, prefix=settings.api_prefix)
app.include_router(work_orders_router, prefix=settings.api_prefix)
app.include_router(evidence_router, prefix=settings.api_prefix)
app.include_router(labels_router, prefix=settings.api_prefix)
app.include_router(operations_router, prefix=settings.api_prefix)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"service": settings.app_name, "version": settings.app_version}
