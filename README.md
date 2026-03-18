# Czech školky local-first starter

Minimal local prototype for:

- pulling official Czech datasets locally,
- loading them into a Podman-hosted PostgreSQL database,
- querying the 10 nearest kindergarten workplaces,
- showing their websites and data-box IDs in a Vite + TypeScript frontend.

## What this prototype does

1. Downloads three official source groups:
   - MŠMT school registry JSON-LD for the whole Czech Republic
   - data-box exports for PO and OVM
   - RÚIAN monthly address-point CSV ZIP with coordinates
2. Flattens kindergarten workplaces (`mistaVyuky`)
3. Joins workplaces to address-point coordinates by `kodRUIAN`
4. Joins workplaces to data-box IDs by `IČO`
5. Stores the result in PostgreSQL
6. Serves an API for nearby search
7. Enriches missing school websites on demand from ARES when the nearby endpoint is called

## Architecture

- `compose.yaml` → local PostgreSQL with Podman
- `backend/etl/load.py` → downloader + parser + loader
- `backend/app/main.py` → FastAPI nearby endpoint
- `frontend/` → Vite + React + TypeScript UI

## Prerequisites

- Python 3.11+
- Node 20+
- Podman
- Internet access during ETL and ARES enrichment

## 1. Start PostgreSQL with Podman

```bash
podman compose up -d db
```

The database starts on `localhost:5432` with:

- database: `skolky`
- user: `skolky`
- password: `skolky`

## 2. Start the backend

```bash
cd backend
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Download and load everything:

```bash
python -m etl.load refresh
```

Start the API:

```bash
uvicorn app.main:app --reload --port 8000
```

Health check:

```bash
curl http://localhost:8000/api/health
```

## 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

## How nearby search works

The browser can provide your current location. The frontend then calls:

```text
GET /api/schools/nearby?lat=50.0755&lon=14.4378&limit=10
```

The backend:

- computes Haversine distance in SQL,
- returns the nearest 10 rows,
- optionally fills missing websites from ARES for the returned IČO values.

## Useful development notes

### The first version intentionally stays minimal

It does **not** yet include:

- filtering to only `příspěvkové organizace`
- deduplication by legal entity vs school vs branch beyond the current workplace flattening key
- catchment-area logic
- reverse website verification by scraping school pages
- caching raw ARES payloads to disk
- Vercel deployment packaging
- map tiles or Leaflet/MapLibre UI

### Next upgrades I would add

1. Add codebook ingestion for legal form and founder type.
2. Materialize `legal_entities` and `school_units` tables separately.
3. Add a filter for public / municipal / `příspěvková organizace` only.
4. Add a local cache table for raw ARES website payloads.
5. Add `pgvector` or PostGIS only if you later need richer geospatial features.

## Source URLs currently wired into ETL

### School registry

```text
https://lkod-ftp.msmt.gov.cz/00022985/250d6b3f-71a2-4441-b8a0-4df141071f13/rssz-cela-cr-2026-01-01.jsonld
```

### Data boxes

```text
https://www.mojedatovaschranka.cz/sds/datafile?format=xml&service=seznam_ds_po
https://www.mojedatovaschranka.cz/sds/datafile?format=xml&service=seznam_ds_ovm
```

### RÚIAN Atom feed

```text
https://atom.cuzk.gov.cz/RUIAN-CSV-ADR-ST/RUIAN-CSV-ADR-ST.xml
```

### ARES endpoints used for website enrichment

```text
https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty-rs/{ICO}
https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/{ICO}
```

## Caveats

- The school-registry URL is pinned to the 2026 whole-Czech export. If MŠMT republishes a new yearly export, update the constant.
- The XML parser for data boxes is intentionally tolerant because the feed is large and namespace-heavy.
- The RÚIAN CSV parser discovers columns by normalized header names. If ČÚZK changes headers, adjust the hints in `load.py`.
- Website enrichment is best-effort. Some schools will still have no website returned.

## Why this is already stronger than a flat paid export

This design keeps **workplaces / branches** (`mistaVyuky`) as first-class records, which is usually the missing piece in many simple commercial spreadsheets. It also gives you a path to geospatial nearest-neighbour search instead of just static mailing lists.
