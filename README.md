# Engine monitoring core

FastAPI service for receiving engine telemetry, storing it, applying a pre-trained condition model and providing current dashboard data.

## Docker

From the `core` directory, build and start the service with a persistent volume for the SQLite database and trained ML model:

```powershell
docker compose up --build -d
```

The API will be reachable at `http://127.0.0.1:8000`. The image is named `vks-engine-core:latest`; stop it with `docker compose down`. The named `core_data` volume preserves telemetry. Before starting the container, create `../model/artifacts/condition_model.joblib` using the separate [model training script](../model/README.md). It is mounted read-only into the runtime container at `/models/condition_model.joblib`.

To build without Compose:

```powershell
docker build -t vks-engine-core:latest .
docker run --rm -p 8000:8000 -v vks-core-data:/data -v ..\model\artifacts:/models:ro vks-engine-core:latest
```

Set `SOURCE_API_URL` and `SOURCE_API_TOKEN` in the shell or in a Compose `.env` file before starting the service when it needs to synchronise with an external telemetry provider.

## Run locally

```powershell
cd core
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API will be at `http://127.0.0.1:8000`; interactive documentation is at `/docs`.
SQLite is used by default and the database file is created automatically. Copy `.env.example` to `.env` or set environment variables to use a remote telemetry API, another database, or a persisted ML model path.

## Main endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/telemetry` | Accept one current telemetry measurement |
| `POST` | `/api/v1/telemetry/batch` | Accept several measurements |
| `POST` | `/api/v1/sync` | Fetch measurements from `SOURCE_API_URL` |
| `GET` | `/api/v1/dashboard/current` | Current data, prediction and recommendations for the dashboard |
| `GET` | `/api/v1/telemetry/history` | Recent persisted measurements |

The runtime service never trains models and exposes no training endpoint. If the configured model file is absent, it returns `model_not_trained`; this is intentional, because it must not present a fake maintenance forecast. Train and validate an artefact outside the final device using the [model training project](../model/README.md), then deploy the resulting `.joblib` file.

## Example telemetry request

```powershell
Invoke-RestMethod -Method Post -ContentType 'application/json' -Uri http://127.0.0.1:8000/api/v1/telemetry -Body @'
{
  "engine_id": "ME-01",
  "rpm": 78.4,
  "engine_load": 62.8,
  "torque_knm": 4815,
  "lube_oil_pressure_bar": 4.26,
  "fuel_consumption_g_kwh": 171.6,
  "exhaust_temp_c": 382,
  "cooling_water_outlet_c": 76.4,
  "vibration_bearing_4_mm_s": 5.8,
  "scavenge_air_pressure_bar": 2.38
}
'@
```

## Model lifecycle

1. Train and validate a model in the separate `model` directory.
2. Copy the approved `.joblib` artefact to the configured `MODEL_PATH`.
3. Start or restart Core; it loads the artefact once at startup.
4. Every incoming measurement is scored and its prediction is stored in the database.

Use a dataset reviewed by marine-engineering experts before relying on a prediction for maintenance decisions.
