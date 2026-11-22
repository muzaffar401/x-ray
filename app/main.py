# FastAPI application initialization and top-level router mounting.
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.config import settings

app = FastAPI(title=settings.APP_NAME)


@app.get("/api/health")
def health() -> dict[str, str]:
    # Minimal health check endpoint
    return {"status": "ok"}


# Serve static directory at "/" with index.html as default landing page
app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
