import os
from dotenv import load_dotenv

# Load root .env
load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env")))

# Database Configuration
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", 5432))
PG_USER = os.getenv("PG_USER", "arnavbansal")
PG_PASSWORD = os.getenv("PG_PASSWORD", "")
PG_DATABASE = os.getenv("PG_DATABASE", "fraud_db")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "fraud_ring_db")

# Security & JWT
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "default-dev-secret-key-replace-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 120))

# CORS
CORS_ORIGIN = os.getenv("CORS_ORIGIN", "http://localhost:5173")
PORT = int(os.getenv("PORT", 8005))

# Model Path
MODEL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models", "fraud_model.joblib"))

