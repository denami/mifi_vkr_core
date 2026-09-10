from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from .config import SOURCE_API_TOKEN, SOURCE_API_URL
from .database import Base, engine, get_session
from .ml import ConditionModel
from .models import Telemetry
from .schemas import BatchTelemetryIn, IngestResponse, TelemetryIn, TrainResponse
from .services import create_prediction, create_telemetry, latest_record, prediction_payload, recommendations

condition_model = ConditionModel()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Engine Condition Monitoring API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict this to dashboard origins in production.
    allow_methods=["GET", "POST"], allow_headers=["*"],
)


def ingest(session: Session, item: TelemetryIn) -> IngestResponse:
    record = create_telemetry(session, item)
    score = condition_model.score(record)
    prediction = create_prediction(session, record, score) if score else None
    session.commit()
    session.refresh(record)
    return IngestResponse(telemetry_id=record.id, prediction=prediction_payload(prediction))


@app.get("/health")
def health() -> dict[str, str | bool]:
    return {"status": "ok", "model_ready": condition_model.ready}


@app.post("/api/v1/telemetry", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
def post_telemetry(item: TelemetryIn, session: Session = Depends(get_session)) -> IngestResponse:
    return ingest(session, item)


@app.post("/api/v1/telemetry/batch")
def post_telemetry_batch(batch: BatchTelemetryIn, session: Session = Depends(get_session)) -> dict[str, Any]:
    results = [ingest(session, item) for item in batch.records]
    return {"accepted": len(results), "records": results}


@app.post("/api/v1/sync")
async def sync_from_source(session: Session = Depends(get_session)) -> dict[str, Any]:
    if not SOURCE_API_URL:
        raise HTTPException(status_code=400, detail="SOURCE_API_URL is not configured.")
    headers = {"Authorization": f"Bearer {SOURCE_API_TOKEN}"} if SOURCE_API_TOKEN else {}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(SOURCE_API_URL, headers=headers)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail=f"Telemetry source request failed: {error}") from error
    records = payload.get("data", []) if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise HTTPException(status_code=502, detail="Source response must be a list or an object with a data list.")
    validated = [TelemetryIn.model_validate(item) for item in records]
    output = [ingest(session, item) for item in validated]
    return {"received": len(output), "telemetry_ids": [item.telemetry_id for item in output]}


@app.post("/api/v1/model/train", response_model=TrainResponse)
def train_model(session: Session = Depends(get_session)) -> TrainResponse:
    try:
        version, samples, positives, accuracy = condition_model.train(session)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return TrainResponse(model_version=version, samples=samples, positive_samples=positives, training_accuracy=round(accuracy, 3))


@app.get("/api/v1/dashboard/current")
def dashboard_current(engine_id: str = Query(default="ME-01"), session: Session = Depends(get_session)) -> dict[str, Any]:
    record = latest_record(session, engine_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"No telemetry found for engine {engine_id}.")
    return {
        "engine_id": record.engine_id,
        "recorded_at": record.recorded_at,
        "telemetry": {
            "rpm": record.rpm, "engine_load": record.engine_load, "torque_knm": record.torque_knm,
            "lube_oil_pressure_bar": record.lube_oil_pressure_bar, "fuel_consumption_g_kwh": record.fuel_consumption_g_kwh,
            "exhaust_temp_c": record.exhaust_temp_c, "cooling_water_outlet_c": record.cooling_water_outlet_c,
            "vibration_bearing_4_mm_s": record.vibration_bearing_4_mm_s,
            "scavenge_air_pressure_bar": record.scavenge_air_pressure_bar,
        },
        "prediction": prediction_payload(record.prediction).model_dump(),
        "recommendations": recommendations(record, record.prediction),
    }


@app.get("/api/v1/telemetry/history")
def telemetry_history(
    engine_id: str = Query(default="ME-01"), limit: int = Query(default=100, ge=1, le=1_000),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    records = session.scalars(
        select(Telemetry).where(Telemetry.engine_id == engine_id).order_by(desc(Telemetry.recorded_at)).limit(limit)
    ).all()
    return [{
        "id": row.id, "recorded_at": row.recorded_at, "rpm": row.rpm,
        "engine_load": row.engine_load, "vibration_bearing_4_mm_s": row.vibration_bearing_4_mm_s,
        "exhaust_temp_c": row.exhaust_temp_c,
        "prediction": prediction_payload(row.prediction).model_dump(),
    } for row in records]
