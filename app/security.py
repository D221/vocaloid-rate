import os

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
