import os

from .base import *  # noqa: F401,F403

DEBUG = os.getenv("DEBUG", "True").lower() == "true"
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS") or ["127.0.0.1", "localhost"]
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS") or [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]
