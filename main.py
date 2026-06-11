"""
╔══════════════════════════════════════════════════════════════════╗
║           NASA OMNI-GATEWAY — FastAPI Backend v7.0.0             ║
║    Equipe: Nícolas · Tiago · Jhonatan — UniCV 2026               ║
║                                                                  ║
║  v7.0.0 — Refatoração Modular:                                   ║
║  · Lógica HTTP separada em routers/core.py                       ║
║  · Endpoints agrupados por domínio em routers/                   ║
║    visual.py · monitoramento.py · ciencia.py                     ║
║  · main.py responsável apenas pela montagem da aplicação         ║
╚══════════════════════════════════════════════════════════════════╝
"""

import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import core
from routers.core import TIMEOUTS, BROWSER_HEADERS
from routers.visual import router as visual_router
from routers.monitoramento import router as monitoramento_router
from routers.ciencia import router as ciencia_router


# ── LIFESPAN: abre e fecha os clientes HTTP persistentes ──────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    for nome, timeout in TIMEOUTS.items():
        core.clients[nome] = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            verify=False,
            headers=BROWSER_HEADERS,
        )
    yield
    await asyncio.gather(*[c.aclose() for c in core.clients.values()])


# ── APLICAÇÃO ─────────────────────────────────────────────────────
app = FastAPI(
    title="NASA Omni-Gateway",
    description=(
        "Gateway FastAPI que intermedia todas as requisições entre o painel web "
        "e as APIs oficiais da NASA. Inclui cache TTL por rota, retry automático, "
        "connection pooling e tratamento de erros estruturado.\n\n"
        "**Equipe:** Nícolas · Tiago · Jhonatan — UniCV 2026"
    ),
    version="7.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ── REGISTRO DOS ROUTERS ──────────────────────────────────────────
app.include_router(visual_router)
app.include_router(monitoramento_router)
app.include_router(ciencia_router)


# ── ROTA RAIZ ─────────────────────────────────────────────────────
@app.get("/", tags=["Status"])
async def root():
    """Health check do gateway."""
    return {
        "status": "🟢 online",
        "projeto": "NASA Omni-Gateway",
        "versao": "7.0.0",
        "equipe": ["Nícolas", "Tiago", "Jhonatan"],
        "instituicao": "UniCV 2026",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)