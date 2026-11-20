# CrowdFlow

CrowdFlow is a modular FastAPI and React application for analysing recorded crowd videos. It uses pretrained YOLO detection and Ultralytics ByteTrack tracking, maps persistent tracks to venue zones, and produces deterministic graph/statistical congestion forecasts.

Phase 1 accepts uploaded recorded video only. It does not integrate live CCTV or use a trained congestion model.

## Setup

From the repository root:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
npm.cmd --prefix frontend install
Copy-Item .env.example .env
```

## Run

Backend (verified alternate local port):

```powershell
py -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
npm.cmd --prefix frontend run dev
```

Open `http://127.0.0.1:5173`. The API documentation is at `http://127.0.0.1:8000/docs`.

## Tests

```powershell
py -m pytest backend/tests
```

## Folder structure

```text
CrowdFlow/
|-- backend/
|   |-- app/
|   |   |-- routers/
|   |   |-- services/
|   |   |-- config.py
|   |   |-- main.py
|   |   |-- schemas.py
|   |   |-- state.py
|   |   `-- ws.py
|   |-- ai_venv/
|   |-- storage/
|   `-- tests/
|-- frontend/
|   |-- src/
|   |   |-- components/
|   |   `-- App.jsx
|   |-- index.html
|   `-- package.json
|-- requirements.txt
|-- .env.example
`-- decisions_taken.md
```

