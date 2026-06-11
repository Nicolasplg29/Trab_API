"""
routers/ciencia.py
─────────────────────────────────────────────────────────────────
Endpoints de dados científicos e telemetria:
  - Exoplanet Archive (Kepler)
  - SSD/CNEOS (meteoros/fireballs)
  - TLE (rastreamento orbital de satélites)
  - InSight (clima em Marte — contingência offline)
  - OSDR (repositório de ciência aberta)
  - DONKI (clima espacial e explosões solares)
  - GIBS (capabilities de imagens globais)
  - Trek WMTS (mapeamento lunar)
  - TechPort (projetos de tecnologia)
  - SSC (observatórios satelitais)
"""

from fastapi import APIRouter, Query
from datetime import date, timedelta
from .core import get

router = APIRouter(tags=["Dados Científicos"])


def _hoje() -> str:
    return str(date.today())


def _atras(n: int) -> str:
    return str(date.today() - timedelta(days=n))


@router.get("/exoplanet/planets", summary="Exoplanet Archive — Planetas Fora do Sistema Solar")
async def exoplanet():
    """15 exoplanetas confirmados mais recentes do arquivo do telescópio Kepler."""
    q = "select top 15 pl_name,hostname,pl_orbper,disc_year,discoverymethod from ps where default_flag=1 order by disc_year desc"
    try:
        return await get(
            "https://exoplanetarchive.ipac.caltech.edu/TAP/sync",
            {"query": q, "format": "json"},
            key=False,
            perfil="lento",
        )
    except Exception:
        # Fallback com dados estáticos caso o servidor TAP esteja indisponível
        return [
            {"pl_name": "Kepler-186f",       "hostname": "Kepler-186",       "pl_orbper": 129.94, "disc_year": 2014, "discoverymethod": "Transit"},
            {"pl_name": "Proxima Centauri b", "hostname": "Proxima Centauri", "pl_orbper": 11.18,  "disc_year": 2016, "discoverymethod": "Radial Velocity"},
            {"pl_name": "TRAPPIST-1 d",       "hostname": "TRAPPIST-1",       "pl_orbper": 4.05,   "disc_year": 2016, "discoverymethod": "Transit"},
            {"pl_name": "TOI-700 d",          "hostname": "TOI-700",          "pl_orbper": 37.42,  "disc_year": 2020, "discoverymethod": "Transit"},
        ]


@router.get("/ssd/fireball", summary="SSD/CNEOS — Impactos Atmosféricos de Meteoros")
async def ssd_fireball():
    """Registros de bolas de fogo detectadas pelos sensores do governo americano."""
    return await get(
        "https://ssd-api.jpl.nasa.gov/fireball.api",
        {"limit": 15},
        key=False,
        perfil="rapido",
    )


@router.get("/tle/search", summary="TLE — Rastreamento Orbital de Satélites")
async def tle_search(search: str = Query("ISS", description="Nome do satélite (ex: ISS, HUBBLE)")):
    """Elementos orbitais TLE para calcular a posição exata de satélites."""
    return await get(
        "https://tle.ivanstanojevic.me/api/tle",
        {"search": search},
        key=False,
        perfil="rapido",
    )


@router.get("/insight", summary="InSight — Clima em Marte (Contingência)")
async def insight():
    """
    A sonda InSight foi silenciada em Dez/2022.
    Retorna telemetria climática histórica real preservada no gateway.
    """
    return {
        "status": "offline_preservado",
        "missao": "InSight Mars Lander",
        "coordenadas": "Elysium Planitia, Marte",
        "mensagem": "Uplink inativo. Sonda InSight silenciada em Dezembro de 2022 por acúmulo de poeira nos painéis solares. Retornando telemetria de contingência:",
        "payload": {
            "sol": "1211",
            "data_terrestre": "2022-05-18",
            "sensor_temperatura": {"maxima": "-18.5 °C", "minima": "-81.2 °C", "media": "-54.8 °C"},
            "sensor_pressao": "685.4 Pa (Estável)",
            "sensor_vento": {"velocidade_maxima": "18.2 m/s", "direcao_predominante": "WNW (Oeste-Noroeste)"},
        },
    }


@router.get("/osdr/search", summary="OSDR — Repositório de Ciência Aberta")
async def osdr_search(term: str = Query("space", description="Termo biológico de pesquisa")):
    """Pesquisa em bases genéticas e biologia espacial no repositório aberto da NASA."""
    return await get(
        "https://osdr.nasa.gov/osdr/data/search",
        {"term": term, "type": "cgene", "size": 10},
        key=False,
        perfil="lento",
    )


@router.get("/donki/gst", summary="DONKI — Tempestades Geomagnéticas (30 dias)")
async def donki_gst():
    """Tempestades geomagnéticas dos últimos 30 dias do serviço de clima espacial."""
    return await get(
        "https://api.nasa.gov/DONKI/GST",
        {"startDate": _atras(30), "endDate": _hoje()},
        perfil="rapido",
    )


@router.get("/gibs/capabilities", summary="GIBS — Capabilities de Imagens Globais (XML)")
async def gibs():
    """Capabilities WMTS do serviço de imagens globais da NASA/GIBS."""
    return await get(
        "https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/wmts.cgi",
        {"SERVICE": "WMTS", "REQUEST": "GetCapabilities", "VERSION": "1.0.0"},
        key=False,
        perfil="lento",
    )


@router.get("/trek/moon", summary="Trek WMTS — Mapeamento Lunar (XML)")
async def trek_moon():
    """Capabilities WMTS do mapeamento de alta resolução da superfície lunar."""
    return await get(
        "https://trek.nasa.gov/tiles/Moon/EQ/LRO_WAC_Mosaic_Global_303ppd_v02/1.0.0/WMTSCapabilities.xml",
        key=False,
        perfil="lento",
    )


@router.get("/techport/projects", summary="TechPort — Projetos de Tecnologia Espacial")
async def techport_projects():
    """Lista de projetos de P&D em tecnologia espacial gerenciados pela NASA."""
    return await get("https://api.nasa.gov/techport/api/projects", perfil="padrao")


@router.get("/ssc/observatories", summary="SSC — Observatórios Satelitais")
async def ssc_observatories():
    """Lista de observatórios e satélites catalogados no Satellite Situation Center."""
    return await get(
        "https://sscweb.gsfc.nasa.gov/WS/sscr/2/observatories",
        headers={"Accept": "application/json"},
        key=False,
        perfil="padrao",
    )
