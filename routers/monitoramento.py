"""
routers/monitoramento.py
─────────────────────────────────────────────────────────────────
Endpoints de monitoramento em tempo real:
  - NeoWs  (asteroides próximos à Terra)
  - EONET  (eventos naturais por satélite)
  - TechTransfer (patentes da NASA)
"""

from fastapi import APIRouter, Query
from typing import Optional
from datetime import date
from .core import get

router = APIRouter(tags=["Monitoramento"])


def _hoje() -> str:
    return str(date.today())


@router.get("/neows/feed", summary="NeoWs — Asteroides Próximos à Terra")
async def neows_feed(
    start_date: Optional[str] = Query(None, description="Data inicial (AAAA-MM-DD)")
):
    """Lista asteroides que passam perto da Terra na data informada."""
    d = start_date or _hoje()
    return await get(
        "https://api.nasa.gov/neo/rest/v1/feed",
        {"start_date": d, "end_date": d},
        perfil="rapido",
    )


@router.get("/eonet/events", summary="EONET — Eventos Naturais Abertos")
async def eonet_events():
    """Monitoramento por satélite de eventos naturais ativos (vulcões, tempestades, icebergs)."""
    return await get(
        "https://eonet.gsfc.nasa.gov/api/v3/events",
        {"status": "open", "limit": 12},
        key=False,
        perfil="rapido",
    )


@router.get("/techtransfer/patent", summary="TechTransfer — Patentes da NASA")
async def tech_transfer(q: str = Query("engine", description="Termo de busca em inglês")):
    """Retorna patentes de engenharia e tecnologia desenvolvidas pela NASA."""
    url = f"https://technology.nasa.gov/api/api/patent/{q}"
    return await get(url, key=False, perfil="padrao")
