# pyFIA Agent

A public-facing AI-powered interface to the USDA Forest Service Forest Inventory and Analysis (FIA) database.

## Features

- 🌲 **Natural Language Queries** - Ask questions about forest inventory in plain English
- 📊 **Validated Statistics** - All estimates match official USFS EVALIDator results
- 📥 **Data Downloads** - Create custom data exports for your own analysis
- 📈 **Visualizations** - Interactive charts and maps (coming soon)

## Tech Stack

- **Frontend**: Next.js 15, Vercel AI SDK, shadcn/ui, Tailwind CSS
- **Backend**: FastAPI, LangChain, Claude Sonnet
- **Data**: [pyFIA](https://github.com/mihiarc/pyfia) (DuckDB/Polars)

## Project Structure

```
pyfia-agent/
├── frontend/          # Next.js application
│   ├── app/           # App Router pages
│   ├── components/    # React components
│   └── lib/           # Utilities
├── backend/           # FastAPI application
│   ├── src/pyfia_api/ # API source code
│   └── data/          # FIA database files (gitignored)
├── docker-compose.yml # Local development
└── README.md
```

## Quick Start

### Prerequisites

- Node.js 20+
- Python 3.11+
- pnpm (for frontend)
- uv (for backend, recommended)

### Development

1. **Clone and setup**:
   ```bash
   git clone https://github.com/yourusername/pyfia-agent.git
   cd pyfia-agent
   ```

2. **Start the backend**:
   ```bash
   cd backend
   cp .env.example .env
   # Add your ANTHROPIC_API_KEY to .env
   uv sync
   uv run uvicorn pyfia_api.main:app --reload
   ```

3. **Start the frontend** (new terminal):
   ```bash
   cd frontend
   cp .env.example .env.local
   pnpm install
   pnpm dev
   ```

4. Open http://localhost:3000

### Docker (Recommended)

```bash
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env
docker compose up
```

## Environment Variables

### Backend (.env)
```
ANTHROPIC_API_KEY=sk-ant-...
CORS_ORIGINS=http://localhost:3000
REDIS_URL=redis://localhost:6379
```

### Frontend (.env.local)
```
BACKEND_URL=http://localhost:8000
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/chat/stream` | POST | Streaming chat with AI agent |
| `/api/v1/query/area` | POST | Query forest area |
| `/api/v1/query/volume` | POST | Query timber volume |
| `/api/v1/query/biomass` | POST | Query biomass/carbon |
| `/api/v1/query/compare` | POST | Compare states |
| `/api/v1/downloads/prepare` | POST | Prepare data download |
| `/api/v1/health` | GET | Health check |

## Example Queries

- "How much forest land is in North Carolina?"
- "Compare timber volume in Georgia, South Carolina, and Florida"
- "What are the top 5 tree species by biomass in Oregon?"
- "Show me carbon stocks in California"
- "Prepare a data download for Alabama"

## Data Source

All data comes from the USDA Forest Service [Forest Inventory and Analysis (FIA)](https://www.fia.fs.usda.gov/) program. Statistics are computed using [pyFIA](https://github.com/mihiarc/pyfia), which implements design-based estimation methods following Bechtold & Patterson (2005).

## License

MIT

## Contributing

Contributions welcome! Please read our contributing guidelines first.
