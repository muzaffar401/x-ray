# FastAPI application initialization and top-level router mounting.
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import Base, engine
from app.routers import reports


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all database tables on application startup
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# Mount API routers
app.include_router(reports.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    # Minimal health check endpoint
    return {"status": "ok"}


# Serve static directory at "/" with index.html as default landing page
app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
