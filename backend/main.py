import os
import joblib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from backend.config import CORS_ORIGIN, MODEL_PATH
from backend.routers import (
    auth_router,
    scoring_router,
    alerts_router,
    rings_router,
    dashboard_router,
    transactions_router
)

app = FastAPI(
    title="Intelligent Fraud Ring Detection API",
    description="Decision-Support Platform for Bank Fraud Analysts (PostgreSQL + MongoDB + XGBoost)",
    version="2.0.0"
)

# Configure CORS strictly for Vite dev origin from .env
origins = [origin.strip() for origin in CORS_ORIGIN.split(",") if origin.strip()]
# Always allow local dev origins
if "http://localhost:5173" not in origins:
    origins.append("http://localhost:5173")
if "http://127.0.0.1:5173" not in origins:
    origins.append("http://127.0.0.1:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup: Load XGBoost model once
@app.on_event("startup")
def startup_event():
    if os.path.exists(MODEL_PATH):
        try:
            bundle = joblib.load(MODEL_PATH)
            print(f"[STARTUP] Loaded XGBoost model from {MODEL_PATH}")
            print(f"[STARTUP] Features: {bundle.get('feature_cols')}")
            print(f"[STARTUP] Metrics: {bundle.get('metrics')}")
        except Exception as e:
            print(f"[STARTUP ERROR] Could not load model: {e}")
    else:
        print(f"[STARTUP WARNING] Model not found at {MODEL_PATH}")

# Include all API Routers
app.include_router(auth_router.router, prefix="/api")
app.include_router(transactions_router.router, prefix="/api")
app.include_router(scoring_router.router, prefix="/api")
app.include_router(alerts_router.router, prefix="/api")
app.include_router(rings_router.router, prefix="/api")
app.include_router(dashboard_router.router, prefix="/api")

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Fraud Ring Detection API",
        "version": "2.0.0"
    }

# Mount static build if present
dist_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
if os.path.exists(dist_dir):
    @app.exception_handler(404)
    async def custom_404_handler(request, exc):
        if not request.url.path.startswith("/api/"):
            index_file = os.path.join(dist_dir, "index.html")
            if os.path.exists(index_file):
                return FileResponse(index_file)
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    app.mount("/", StaticFiles(directory=dist_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    from backend.config import PORT
    host = os.getenv("HOST", "127.0.0.1")
    reload = os.getenv("RELOAD", "false").lower() in ("true", "1")
    uvicorn.run("backend.main:app", host=host, port=PORT, reload=reload)
