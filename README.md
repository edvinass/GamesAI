# GamesAI

Free online multiplayer games with AI players. Built with Vue 3, FastAPI, and PostgreSQL.

## Games

- **Codenames** — Team word guessing with optional AI spymasters and operatives

## How to Play

1. Enter your nickname and click **ENTER GAME**
2. Select your preferred game settings and start the game
3. Connect with your friends using your favorite audio or video chat
4. Share the room URL with your friends
5. Enjoy the game!

## Quick Start (Docker)

```bash
cp .env.example .env
# Add your DEEPSEEK_API_KEY to .env for AI players

docker compose up --build
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs

## Local Development (without Docker)

### Prerequisites

- Python 3.12+
- Node.js 22+
- PostgreSQL 16+

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Set DATABASE_URL in .env (see .env.example)
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` and `/ws` to `http://localhost:8000`. Update `frontend/vite.config.ts` proxy target if needed.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string (asyncpg) |
| `DEEPSEEK_API_KEY` | DeepSeek API key for AI players |
| `DEEPSEEK_BASE_URL` | DeepSeek API base URL (default: `https://api.deepseek.com`) |
| `DEEPSEEK_MODEL` | Model name (default: `deepseek-v4-pro`) |
| `DEEPSEEK_THINKING` | Enable chain-of-thought reasoning (default: `true`) |
| `DEEPSEEK_REASONING_EFFORT` | Reasoning depth: `high` or `max` (default: `max`) |
| `SECRET_KEY` | Session signing key |
| `CORS_ORIGINS` | Comma-separated allowed origins |

## Deploy to Railway

GamesAI deploys as **three Railway services**: Postgres, backend, and frontend. The frontend Caddy container serves the Vue app and proxies `/api` and `/ws` to the backend over Railway private networking.

### 1. Create the project

1. Create a new Railway project from this repo.
2. Add a **Postgres** plugin.
3. Add a **backend** service with Root Directory set to `backend`.
4. Add a **frontend** service with Root Directory set to `frontend`.

Each service picks up its [`railway.toml`](backend/railway.toml) for health checks.

### 2. Configure environment variables

**backend service**

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | Reference from Postgres plugin |
| `SECRET_KEY` | Strong random value |
| `DEEPSEEK_API_KEY` | Your DeepSeek API key |
| `CORS_ORIGINS` | Frontend public URL |

**frontend service**

| Variable | Value |
|----------|-------|
| `BACKEND_URL` | `http://${{backend.RAILWAY_PRIVATE_DOMAIN}}:${{backend.PORT}}` |

Replace `backend` in the reference with your backend service name if different.

### 3. Publish the frontend URL

Generate a public domain for the **frontend** service. That URL is what players use to create and join rooms.

The backend does not need a public domain for normal gameplay (Caddy proxies API and WebSocket traffic).

### 4. Verify the deployment

- `https://<frontend>/api/health` returns `{"status":"ok"}`
- `https://<frontend>/` loads the app
- Creating a room opens a WebSocket at `wss://<frontend>/ws/rooms/...`
- Deep links like `/room/<id>` load correctly

See [`.env.example`](.env.example) for the full variable reference.

## Architecture

- **Frontend:** Vue 3 + Vite + Pinia + Vue Router
- **Backend:** FastAPI + SQLAlchemy + Alembic
- **Database:** PostgreSQL
- **Real-time:** WebSockets for lobby and game state
- **AI:** DeepSeek API for Codenames spymaster/operative logic

## Adding New Games

Implement the `GamePlugin` interface in `backend/app/games/` and register in `backend/app/games/registry.py`. Add a Vue component under `frontend/src/games/`.

## Legal

Codenames is a trademark of Czech Games Edition. This project implements Codenames-style gameplay with an original UI and open word lists.
