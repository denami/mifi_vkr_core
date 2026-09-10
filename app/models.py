from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Telemetry(Base):
    __tablename__ = "telemetry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    engine_id: Mapped[str] = mapped_column(String(64), index=True, default="ME-01")
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    rpm: Mapped[float] = mapped_column(Float)
    engine_load: Mapped[float] = mapped_column(Float)
    torque_knm: Mapped[float] = mapped_column(Float)
    lube_oil_pressure_bar: Mapped[float] = mapped_column(Float)
    fuel_consumption_g_kwh: Mapped[float] = mapped_column(Float)
    exhaust_temp_c: Mapped[float] = mapped_column(Float)
    cooling_water_outlet_c: Mapped[float] = mapped_column(Float)
    vibration_bearing_4_mm_s: Mapped[float] = mapped_column(Float)
    scavenge_air_pressure_bar: Mapped[float] = mapped_column(Float)
    failure_within_72h: Mapped[bool | None] = mapped_column(Boolean, nullable=True, index=True)

    prediction: Mapped["Prediction | None"] = relationship(back_populates="telemetry", uselist=False, cascade="all, delete-orphan")


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telemetry_id: Mapped[int] = mapped_column(ForeignKey("telemetry.id"), unique=True, index=True)
    model_version: Mapped[str] = mapped_column(String(80))
    condition: Mapped[str] = mapped_column(String(32))
    failure_probability: Mapped[float] = mapped_column(Float)
    wear_index: Mapped[float] = mapped_column(Float)
    predicted_component: Mapped[str] = mapped_column(String(128))
    remaining_useful_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    telemetry: Mapped[Telemetry] = relationship(back_populates="prediction")
