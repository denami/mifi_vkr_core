# Engine monitoring core

FastAPI service for receiving engine telemetry, storing it, training a condition model and providing current dashboard data.

## Docker

From the `core` directory, build and start the service with a persistent volume for the SQLite database and trained ML model:

```powershell
docker compose up --build -d
```

The API will be reachable at `http://127.0.0.1:8000`. The image is named `vks-engine-core:latest`; stop it with `docker compose down`. The named `core_data` volume is preserved after stopping the container, so historical telemetry and the trained model are not lost.

To build without Compose:

```powershell
docker build -t vks-engine-core:latest .
docker run --rm -p 8000:8000 -v vks-core-data:/data vks-engine-core:latest
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
| `POST` | `/api/v1/model/train` | Train the failure-risk model on labelled data |
| `GET` | `/api/v1/dashboard/current` | Current data, prediction and recommendations for the dashboard |
| `GET` | `/api/v1/telemetry/history` | Recent persisted measurements |

The `failure_within_72h` label is required only for historical data used for training: `true` means a fault happened within the next 72 hours, `false` means it did not. The service will return `model_not_trained` predictions until it has at least 20 labelled examples with both label classes. This is intentional: an untrained model must not present a fake maintenance forecast.

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

1. Import historical labelled measurements through the regular telemetry endpoint.
2. Train a `RandomForestClassifier` with `POST /api/v1/model/train`.
3. Every incoming measurement is scored automatically and its prediction is stored in the database.
4. Retrain periodically as new labelled maintenance outcomes become available.

Use a dataset reviewed by marine-engineering experts before relying on a prediction for maintenance decisions.
