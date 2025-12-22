# pyfia-agent

AI-powered natural language interface to the USDA Forest Service FIA database.

## Project Structure

```
pyfia-agent/
├── frontend/          # Next.js 15 + React 19 (Netlify)
├── backend/           # FastAPI Python API (Render)
└── data/              # Local FIA DuckDB cache (gitignored)
```

## Deployment Infrastructure

### Render (Backend API)

| Property | Value |
|----------|-------|
| Service Name | `pyfia-api` |
| Service ID | `srv-d53fn7khg0os738rbgr0` |
| URL | https://pyfia-api.onrender.com |
| Dashboard | https://dashboard.render.com/web/srv-d53fn7khg0os738rbgr0 |
| Region | Oregon |
| Plan | Standard (2GB RAM) |
| Runtime | Python 3.11 |
| Root Directory | `backend` |
| Health Check | `/health` |
| Auto Deploy | Yes (on push to `main`) |
| Repository | https://github.com/mihiarc/pyfia-agent |

**Build/Start Commands:**
```bash
# Build
pip install -r requirements.txt && pip install -e .

# Start
uvicorn pyfia_api.main:app --host 0.0.0.0 --port $PORT
```

**Environment Variables (Render):**
- `ANTHROPIC_API_KEY` - Claude API key (secret)
- `MOTHERDUCK_TOKEN` - MotherDuck authentication (secret)
- `CORS_ORIGINS` - Allowed origins for CORS
- `FIA_S3_BUCKET`, `S3_ENDPOINT_URL`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` - R2/S3 storage (optional)
- `LOG_LEVEL` - Logging level (default: INFO)

### Netlify (Frontend)

| Property | Value |
|----------|-------|
| Site Name | `pyfia-agent` |
| Site ID | `60dcedd5-a264-4e59-9fdc-4fe8c7fc9d7f` |
| URL | https://pyfia-agent.netlify.app |
| Dashboard | https://app.netlify.com/projects/pyfia-agent |
| Build Command | `npm run build` |
| Publish Directory | `.next` |
| Node Version | 20 |
| Plugin | `@netlify/plugin-nextjs` |

**Environment Variables (Netlify):**
- `NEXT_PUBLIC_API_URL` - Backend API URL (https://pyfia-api.onrender.com)

### MotherDuck (Serverless DuckDB)

- **Purpose:** Serverless analytical database for FIA data queries
- **Dashboard:** https://app.motherduck.com
- **Authentication:** `MOTHERDUCK_TOKEN` environment variable
- **Usage:** Primary data tier for production (replaces local DuckDB files)

## Storage Tiers

1. **Hot (Local):** In-memory/local disk cache, <100ms latency
2. **Warm (S3/R2):** Pre-built DuckDB files, moderate latency
3. **Cold (MotherDuck):** Serverless DuckDB, on-demand queries
4. **Origin (FIA DataMart):** USDA source data, slowest but always fresh

## Development

```bash
# Install dependencies
make install

# Run locally (frontend + backend)
make dev

# Run backend only
cd backend && uv run uvicorn pyfia_api.main:app --reload

# Run frontend only
cd frontend && npm run dev

# Run tests
make test

# Lint
make lint
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/health/ready` | GET | Readiness (pyFIA + Anthropic) |
| `/api/v1/chat/stream` | POST | Streaming chat with Claude |
| `/api/v1/query/area` | POST | Forest area queries |
| `/api/v1/query/volume` | POST | Timber volume queries |
| `/api/v1/query/biomass` | POST | Biomass/carbon queries |
| `/api/v1/query/tpa` | POST | Trees per acre queries |
| `/api/v1/query/compare` | POST | Multi-state comparisons |
| `/api/v1/downloads/prepare` | POST | Data export |
| `/debug/query` | GET | Debug MotherDuck |
| `/debug/storage` | GET | Debug storage config |

## Tech Stack

- **Frontend:** Next.js 15, React 19, Tailwind CSS, shadcn/ui, Vercel AI SDK
- **Backend:** FastAPI, Pydantic v2, LangChain, Claude API
- **Data:** pyFIA, DuckDB, Polars, MotherDuck
- **Deployment:** Render (backend), Netlify (frontend), Cloudflare R2 (storage)
