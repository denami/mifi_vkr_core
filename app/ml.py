from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import MODEL_PATH
from .models import Telemetry

FEATURES = (
    "rpm", "engine_load", "torque_knm", "lube_oil_pressure_bar",
    "fuel_consumption_g_kwh", "exhaust_temp_c", "cooling_water_outlet_c",
    "vibration_bearing_4_mm_s", "scavenge_air_pressure_bar",
)


@dataclass
class Score:
    condition: str
    failure_probability: float
    wear_index: float
    predicted_component: str
    remaining_useful_hours: int
    confidence: float
    model_version: str


class ConditionModel:
    """Persists a supervised failure-risk model and scores incoming telemetry."""

    def __init__(self, model_path: Path = MODEL_PATH):
        self.model_path = model_path
        self.model: RandomForestClassifier | None = None
        self.version: str | None = None
        self.load()

    @property
    def ready(self) -> bool:
        return self.model is not None

    def load(self) -> None:
        if not self.model_path.exists():
            return
        saved = joblib.load(self.model_path)
        self.model = saved["model"]
        self.version = saved["version"]

    def train(self, session: Session) -> tuple[str, int, int, float]:
        rows = session.scalars(
            select(Telemetry).where(Telemetry.failure_within_72h.is_not(None))
        ).all()
        if len(rows) < 20:
            raise ValueError("Need at least 20 labelled measurements before training.")
        labels = np.array([row.failure_within_72h for row in rows], dtype=int)
        if len(np.unique(labels)) < 2:
            raise ValueError("Training data must include both normal and failure examples.")
        matrix = np.array([[getattr(row, feature) for feature in FEATURES] for row in rows])
        model = RandomForestClassifier(
            n_estimators=300, max_depth=10, min_samples_leaf=2,
            class_weight="balanced", random_state=42, n_jobs=-1,
        )
        model.fit(matrix, labels)
        accuracy = float(model.score(matrix, labels))
        version = "rf-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": model, "version": version, "features": FEATURES}, self.model_path)
        self.model, self.version = model, version
        return version, len(rows), int(labels.sum()), accuracy

    def score(self, telemetry: Telemetry) -> Score | None:
        if not self.model:
            return None
        values = np.array([[getattr(telemetry, feature) for feature in FEATURES]])
        probability = float(self.model.predict_proba(values)[0, 1])
        condition = "healthy" if probability < .18 else "watch" if probability < .45 else "critical"
        # Derived values are deliberately conservative and are not a replacement
        # for a manufacturer-approved remaining-life calculation.
        rul = max(24, round(1_500 * (1 - probability) ** 2))
        component = self._most_likely_component(telemetry)
        confidence = min(.98, .55 + abs(probability - .5) * .8)
        return Score(condition, probability, probability * 100, component, rul, confidence, self.version or "unknown")

    @staticmethod
    def _most_likely_component(row: Telemetry) -> str:
        if row.vibration_bearing_4_mm_s >= 5.0:
            return "bearing_4"
        if row.lube_oil_pressure_bar < 3.4:
            return "lubrication_system"
        if row.exhaust_temp_c > 410:
            return "exhaust_valve_or_injector"
        if row.scavenge_air_pressure_bar < 1.7:
            return "scavenge_air_system"
        return "main_engine"
