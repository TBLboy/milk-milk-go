from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse

from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.master_data import router as master_data_router
from app.api.work_orders import router as work_orders_router
from app.api.work_order_requests import router as work_order_requests_router
from app.api.evidence import router as evidence_router
from app.api.labels import router as labels_router
from app.api.operations import router as operations_router
from app.api.approvals import router as approvals_router
from app.api.settings import router as settings_router
from app.api.bug_reports import router as bug_reports_router
from app.core.config import get_settings
from app.db.models import initialize_database


@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize_database()
    yield


settings = get_settings()
app = FastAPI(title="牧衡辅料称重防错系统", version=settings.app_version, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix=settings.api_prefix)
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(master_data_router, prefix=settings.api_prefix)
app.include_router(work_orders_router, prefix=settings.api_prefix)
app.include_router(work_order_requests_router, prefix=settings.api_prefix)
app.include_router(evidence_router, prefix=settings.api_prefix)
app.include_router(labels_router, prefix=settings.api_prefix)
app.include_router(operations_router, prefix=settings.api_prefix)
app.include_router(approvals_router, prefix=settings.api_prefix)
app.include_router(settings_router, prefix=settings.api_prefix)
app.include_router(bug_reports_router, prefix=settings.api_prefix)

@app.get("/", include_in_schema=False, response_model=None)
def root() -> FileResponse | dict[str, str]:
    index = settings.frontend_dir / "index.html"
    if index.is_file():
        return FileResponse(index)
    return {"service": settings.app_name, "version": settings.app_version}


@app.api_route(
    "/{full_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    include_in_schema=False,
    response_model=None,
)
def web_admin(request: Request, full_path: str) -> FileResponse:
    if request.method != "GET" or full_path.startswith(("api/", "docs", "redoc", "openapi.json")):
        raise HTTPException(status_code=404, detail="Not Found")

    frontend_root = settings.frontend_dir.resolve()
    candidate = (frontend_root / full_path).resolve()
    if candidate.is_file() and (candidate == frontend_root or frontend_root in candidate.parents):
        return FileResponse(candidate)

    index = frontend_root / "index.html"
    if index.is_file():
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Not Found")
