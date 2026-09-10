from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from .ml import ConditionModel, Score
from .models import Prediction, Telemetry
from .schemas import PredictionOut, TelemetryIn


def create_telemetry(session: Session, item: TelemetryIn) -> Telemetry:
    record = Telemetry(**item.model_dump())
    session.add(record)
    session.flush()
    return record


def create_prediction(session: Session, record: Telemetry, score: Score) -> Prediction:
    prediction = Prediction(
        telemetry_id=record.id, model_version=score.model_version, condition=score.condition,
        failure_probability=score.failure_probability, wear_index=score.wear_index,
        predicted_component=score.predicted_component,
        remaining_useful_hours=score.remaining_useful_hours, confidence=score.confidence,
    )
    session.add(prediction)
    session.flush()
    return prediction


def prediction_payload(prediction: Prediction | None) -> PredictionOut:
    if not prediction:
        return PredictionOut(status="model_not_trained")
    return PredictionOut(
        status="ready", model_version=prediction.model_version, condition=prediction.condition,
        failure_probability=round(prediction.failure_probability, 4), wear_index=round(prediction.wear_index, 1),
        predicted_component=prediction.predicted_component,
        remaining_useful_hours=prediction.remaining_useful_hours, confidence=round(prediction.confidence, 3),
    )


def latest_record(session: Session, engine_id: str) -> Telemetry | None:
    return session.scalar(
        select(Telemetry).where(Telemetry.engine_id == engine_id).order_by(desc(Telemetry.recorded_at)).limit(1)
    )


def recommendations(record: Telemetry, prediction: Prediction | None) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    if record.vibration_bearing_4_mm_s >= 5.0:
        result.append({"priority": "high", "title": "Inspect bearing 4", "detail": "Vibration is above the configured watch threshold of 5.0 mm/s."})
    if record.lube_oil_pressure_bar < 3.4:
        result.append({"priority": "high", "title": "Check lubrication pressure", "detail": "Verify oil level, filter differential pressure and pump condition."})
    if record.fuel_consumption_g_kwh > 170:
        result.append({"priority": "medium", "title": "Review fuel injection", "detail": "Specific fuel consumption is above the nominal operating band."})
    if prediction and prediction.failure_probability >= .45:
        result.append({"priority": "high", "title": "Plan maintenance window", "detail": "The ML failure-risk forecast is elevated; review the relevant component before the next voyage leg."})
    if not result:
        result.append({"priority": "low", "title": "Continue normal monitoring", "detail": "No active maintenance recommendation has been triggered."})
    return result
