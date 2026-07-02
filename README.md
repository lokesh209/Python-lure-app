# Python Lure App

Single cross-platform pipeline that replaces the manual juggling of AddaxAI,
Globus, HiPerGator terminal, and Timelapse. SD card in → tagged CSV out.

## What it does

```
SD card  ─►  app ingests + verifies  ─►  MegaDetector  ─►  review + tag  ─►  CSV
                  (form)                   (HiPerGator)      (in browser)      (DBExport.py
                                                                                schema)
```

Every stage of the lab's existing protocol, in one window. Mirrors the existing
folder convention (`MM-DD_<location>_<site>_<treatment>_<interval>`) and the
`Needs_MegaDetector → Needs_ID → Done_ID_without_CSV → Done_ID` directory pipeline
so the lab's R analysis (`ActivityViz.Rmd`) keeps working unchanged.

## Quick start

### macOS / Linux
```bash
./scripts/run.sh
```

### Windows
```bat
scripts\run.bat
```

The first run installs Python dependencies into `backend/.venv`, builds the
React bundle to `frontend/dist`, and opens <http://127.0.0.1:8000> in your
browser. Subsequent runs are instant.

### Dev mode (hot reload, two processes)
```bash
./scripts/dev.sh
```
Backend on `:8000`, Vite dev server on `:5173` with `/api` and `/ws` proxied.

## Configuration

Copy `backend/.env.example` to `backend/.env` and edit:

```bash
LURE_DATA_ROOT=/Volumes/TOSHIBA EXT/PythonCams   # or wherever projects live
LURE_DETECTOR=mock                                # mock | hipergator
LURE_CONF_THRESHOLD=0.05                          # MegaDetector confidence cutoff

HIPERGATOR_USER=                                  # GatorLink username
HIPERGATOR_SSH_KEY_PATH=                          # ~/.ssh/id_ed25519
```

## Detector backends

| Backend | Status | Notes |
|---|---|---|
| `mock` | ✅ ready | Fakes detections so the rest of the app is testable without HiPerGator. |
| `hipergator` | 🚧 stub | Wires up once McCleery provides credentials and the working `run_pydetector_batch.sbatch`. |

## Project layout

```
backend/
  app/
    api/         FastAPI routers
    core/        config, db, websocket manager
    detectors/   mock + hipergator
    services/    ingest, json parser, csv export, folder naming
    models.py    SQLModel tables
    main.py      FastAPI entry
  requirements.txt
  .env.example

frontend/
  src/
    pages/       Dashboard, NewProject, Project, Review, Settings
    components/  Layout, BboxCanvas, StageBadge
    lib/        api client, ws client, types
  package.json
  vite.config.ts

sbatch/
  run_pydetector_batch.template.sbatch   # parameterized SLURM script

scripts/
  run.sh / run.bat   # production launch
  dev.sh             # hot-reload dev mode
```

## What still needs lab input

1. **HiPerGator credentials** (the username, almost certainly `jones.m`).
2. **The current working `run_pydetector_batch.sbatch`** — drop it into
   `sbatch/` so we can parameterize it correctly (account, partition, conda
   env, exact arguments to MegaDetector).
3. **Confirmation of the SSH-key approach** with UFRC. Once approved, paste
   the laptop's `~/.ssh/id_ed25519.pub` into `~jones.m/.ssh/authorized_keys`
   on HiPerGator and detection becomes one-click.

Until then the app runs fully end-to-end with the `mock` detector.
