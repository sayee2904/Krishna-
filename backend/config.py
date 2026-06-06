"""Configuration loading for the krish backend.

Loads environment variables from a local .env file (creating it from
.env.example on first run) and exposes them with sensible defaults.
"""

import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

# Project root is the parent of the backend/ package directory.
ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"
ENV_EXAMPLE_PATH = ROOT_DIR / ".env.example"

# Bootstrap: copy .env.example -> .env on first run so the app has config.
if not ENV_PATH.exists() and ENV_EXAMPLE_PATH.exists():
    shutil.copyfile(ENV_EXAMPLE_PATH, ENV_PATH)

load_dotenv(ENV_PATH)

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
USER_NAME = os.getenv("USER_NAME", "friend")
