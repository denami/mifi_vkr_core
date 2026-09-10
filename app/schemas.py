from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator


class TelemetryIn(BaseModel):
    engine_id: str = Field(default="ME-01", min_length=1, max_length=64)
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    rpm: float = Field(ge=0, le=250)
    engine_load: float = Field(ge=0, le=120, description="Percent of MCR")
    torque_knm: float = Field(ge=0, le=100_000)
    lube_oil_pressure_bar: float = Field(ge=0, le=20)
    fuel_consumption_g_kwh: float = Field(ge=0, le=500)
    exhaust_temp_c: float = Field(ge=-20, le=1_200)
    cooling_water_outlet_c: float = Field(ge=-20, le=200)
    vibration_bearing_4_mm_s: float = Field(ge=0, le=100)
    scavenge_air_pressure_bar: float = Field(ge=0, le=20)
    @field_validator("recorded_at")
    @classmethod
    def must_have_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class BatchTelemetryIn(BaseModel):
    records: list[TelemetryIn] = Field(min_length=1, max_length=5_000)


class PredictionOut(BaseModel):
    status: str
    model_version: str | None = None
    condition: str | None = None
    failure_probability: float | None = None
    wear_index: float | None = None
    predicted_component: str | None = None
    remaining_useful_hours: int | None = None
    confidence: float | None = None


class IngestResponse(BaseModel):
    telemetry_id: int
    prediction: PredictionOut
