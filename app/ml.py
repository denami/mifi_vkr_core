from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np

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
    """Loads a pre-trained failure-risk model and scores incoming telemetry."""

    def __init__(self, model_path: Path = MODEL_PATH):
        self.model_path = model_path
        self.model: Any | None = None
        self.version: str | None = None
        self.load()

    @property
    def ready(self) -> bool:
        return self.model is not None

    def load(self) -> None:
        if not self.model_path.exists():
            return
        saved = joblib.load(self.model_path)
        if tuple(saved.get("features", ())) != FEATURES:
            raise ValueError(f"Model at {self.model_path} has an incompatible feature schema.")
        self.model = saved["model"]
        self.version = saved["version"]

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
