# FastAPI application initialization and top-level router mounting.
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import Base, engine
from app.routers import auth, reports


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all database tables on application startup
    Base.metadata.create_all(bind=engine)
    # Ensure SQLite column migrations for created_by
    with engine.connect() as conn:
        try:
            cols = [c[1] for c in conn.exec_driver_sql("PRAGMA table_info(reports)").fetchall()]
            if cols and "created_by" not in cols:
                conn.exec_driver_sql("ALTER TABLE reports ADD COLUMN created_by INTEGER REFERENCES users(id)")
                conn.commit()
        except Exception:
            pass
    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# Mount API routers
app.include_router(auth.router)
app.include_router(reports.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    # Minimal health check endpoint
    return {"status": "ok"}


# Serve static directory at "/" with index.html as default landing page
app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
