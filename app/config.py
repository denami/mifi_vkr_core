from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'engine_monitor.db'}")
SOURCE_API_URL = os.getenv("SOURCE_API_URL")
SOURCE_API_TOKEN = os.getenv("SOURCE_API_TOKEN")
MODEL_PATH = Path(os.getenv("MODEL_PATH", str(BASE_DIR / "artifacts" / "condition_model.joblib")))
