# متجر زكي — Smart Store AI Agent

AI-powered shopping assistant (Egyptian Arabic) with a LangGraph agent, hybrid
product search (pgvector + Cohere), voice/image understanding (Gemini), and
WhatsApp order delivery (Twilio).

## Stack

| Layer      | Tech                                                            |
|------------|-----------------------------------------------------------------|
| Backend    | FastAPI · SQLAlchemy 2 (async) · asyncpg                        |
| DB         | PostgreSQL 16 + pgvector (`Vector(1024)`)                       |
| Agent      | LangGraph state machine (`deepseek-v4-flash-0731` via SovereignEG / OpenAI-compatible API) |
| Embeddings | Cohere `embed-multilingual-v3.0` (1024d)                        |
| STT/Vision | Gemini `gemini-3.1-flash-lite` (google-genai SDK)               |
| Frontend   | Static HTML/CSS/JS served by nginx (proxies `/api` → backend)   |
| Deploy     | Docker Compose (db + seed + backend + frontend)                 |

## Quick start

```bash
cp .env.example .env          # fill in your API keys (see below)

# -- keys needed --
# SOVEREIGNEG_API_KEY : agent LLM endpoint
# GEMINI_API_KEY      : voice → text (STT) + image vision
# COHERE_API_KEY      : semantic search embeddings
# TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_WHATSAPP_NUMBER : WhatsApp order alerts

docker compose up --build --wait   # also runs the one-shot seeder

# open
#   http://localhost:8080   → frontend (chat + admin tabs)
#   http://localhost:8000/docs → Swagger (backend)
```

The app degrades gracefully when keys are missing: keyword search still works,
voice/image returns a clear error, and Twilio logs instead of sending.

## Local development (without Docker)

```bash
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 PYTHONPATH=backend \
  python -m app.seed                      # wipe + seed 5 products, 13 stores
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 PYTHONPATH=backend \
  python -m uvicorn app.main:app --port 8000 --reload
pytest                                    # 14 tests, no DB required
```

## Architecture

```
 FastAPI router → ChatService → LangGraph (load_context → route_intent
   → search / category / nearby / purchase → respond)
       └───────── Repository layer → PostgreSQL + pgvector
       └───────── Service layer (SearchService hybrid, OrderService, Twilio)
       └───────── Core (LLM via httpx, Cohere embeddings, Gemini)
```

Design patterns: Repository, Service layer, Factory (singleton LLM/embeddings),
Strategy (semantic → keyword → category search), dependency injection
(`Depends`), state-machine agent (LangGraph).

## Layout

```
backend/
  app/
    core/          # config, logging, llm, embeddings
    db/            # engine/session, models, repositories
    services/      # search (hybrid), orders, location, voice, vision, twilio, chat
    agents/        # langgraph state, prompts, nodes, graph
    schemas/       # pydantic DTOs + serializers
    api/           # routers (chat, voice, image, admin-*, whatsapp, twilio_webhook)
    main.py, seed.py
  tests/
frontend/          # static app + nginx (Dockerfile, nginx.conf)
docker-compose.yml # db · seed · backend · frontend
```