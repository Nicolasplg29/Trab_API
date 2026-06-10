"""
╔══════════════════════════════════════════════════════════════════╗
║           NASA OMNI-GATEWAY — FastAPI Backend v6.8.3             ║
║    Equipe: Nícolas · Tiago · Jhonatan — UniCV 2026               ║
║                                                                  ║
║  v6.8.3 — Hotfix encoding Windows & Retry Loop (503):            ║
║  · Decode UTF-8 explícito via r.content (não r.json())           ║
║  · Catch ampliado: JSONDecodeError + UnicodeDecodeError           ║
║  · XML preview sanitizado para ASCII puro                        ║
║  · Loop de retentativa automática para erros 502/503/504         ║
╚══════════════════════════════════════════════════════════════════╝
"""

from fastapi import FastAPI, HTTPException, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import httpx
import asyncio
import time
import json as _json
from datetime import date, timedelta
from contextlib import asynccontextmanager

API_KEY = "uU0HtIuSrObhlCycbYJGo2NhSph7mBOVnj8j05Jc"

# ──────────────────────────────────────────────────────────────────
#  CONFIGURAÇÃO DE TIMEOUTS POR CATEGORIA DE ENDPOINT
#  Rotas lentas ou instáveis falham mais rápido sem segurar o client
# ──────────────────────────────────────────────────────────────────
TIMEOUTS = {
    "padrao":   25.0,   # Maioria das rotas da NASA
    "rapido":   20.0,   # APOD, NeoWs, DONKI, EONET — servidores da NASA podem demorar
    "lento":    40.0,   # GIBS, Trek, OSDR, Exoplanet — XML pesado ou TAP lento
}

# ──────────────────────────────────────────────────────────────────
#  CACHE EM MEMÓRIA COM TTL
#  Evita refazer a mesma requisição enquanto os dados continuam válidos.
#  Chave = (url, params_frozen) → (timestamp, resultado)
# ──────────────────────────────────────────────────────────────────

# TTL em segundos para cada prefixo de URL
_TTL_MAP = {
    "apod":             300,    # 5 min — imagem do dia muda 1x/dia
    "neo":              120,    # 2 min — feed de asteróides
    "DONKI":            180,    # 3 min
    "eonet":            120,    # 2 min — eventos abertos
    "EPIC":             300,    # 5 min
    "exoplanet":        3600,   # 1 hora — catálogo científico, muito estável
    "gibs":             3600,   # 1 hora — capabilities XML quase não muda
    "fireball":         600,    # 10 min
    "techport":         600,    # 10 min
    "technology.nasa":  600,    # 10 min — patentes
    "ivanstanojevic":   60,     # 1 min — TLE muda com frequência
    "trek.nasa":        3600,   # 1 hora — WMTS capabilities
    "images-api":       300,    # 5 min — busca na biblioteca
    "osdr":             300,    # 5 min
}

_cache: dict[str, tuple[float, object]] = {}

def _ttl_para(url: str) -> int:
    """Retorna o TTL adequado para a URL baseado no mapa acima."""
    for fragmento, ttl in _TTL_MAP.items():
        if fragmento in url:
            return ttl
    return 60  # padrão conservador de 1 minuto para URLs não mapeadas

def _cache_key(url: str, params: dict) -> str:
    return url + "|" + "&".join(f"{k}={v}" for k, v in sorted((params or {}).items()))

def _cache_get(key: str, ttl: int):
    entry = _cache.get(key)
    if entry and (time.monotonic() - entry[0]) < ttl:
        return entry[1]
    return None

def _cache_set(key: str, value):
    _cache[key] = (time.monotonic(), value)


# ──────────────────────────────────────────────────────────────────
#  CLIENTES HTTP PERSISTENTES
#  Um por perfil de timeout para evitar criar novos clients no fallback
# ──────────────────────────────────────────────────────────────────
_clients: dict[str, httpx.AsyncClient] = {}

_BROWSER_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _clients
    for nome, timeout in TIMEOUTS.items():
        _clients[nome] = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            verify=False,
            headers=_BROWSER_HEADERS,
        )
    yield
    await asyncio.gather(*[c.aclose() for c in _clients.values()])


app = FastAPI(
    title="NASA Omni-Gateway",
    description="Gateway FastAPI com lifespan pooling, cache TTL por rota e timeouts individuais.",
    version="6.8.3",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────────────────────────
#  MOTOR HTTP ASSÍNCRONO UNIVERSAL COM RETRY, CACHE E DIAGNÓSTICO
# ──────────────────────────────────────────────────────────────────
async def _get(
    url: str,
    params: dict = None,
    key: bool = True,
    headers: dict = None,
    perfil: str = "padrao",
):
    p = dict(params or {})
    h = dict(headers or {})
    if key:
        p["api_key"] = API_KEY

    # Verifica cache antes de ir à rede
    cache_key = _cache_key(url, p)
    ttl = _ttl_para(url)
    cached = _cache_get(cache_key, ttl)
    if cached is not None:
        return cached

    # Seleciona o cliente correto; usa "padrao" se o perfil não estiver disponível
    client = _clients.get(perfil) or _clients.get("padrao") or httpx.AsyncClient(
        timeout=TIMEOUTS["padrao"], follow_redirects=True, verify=False, headers=_BROWSER_HEADERS
    )

    max_retries = 3
    for tentativa in range(max_retries):
        try:
            r = await client.get(url, params=p, headers=h)
            
            # Se for um erro temporário do servidor remoto e ainda temos tentativas de retransmissão...
            if r.status_code in (502, 503, 504) and tentativa < max_retries - 1:
                # Espera incremental curta antes de retransmitir: 0.5s na primeira falha, 1.0s na segunda
                await asyncio.sleep(0.5 * (tentativa + 1))
                continue

            r.raise_for_status()

            # Força decode UTF-8 explícito — evita falhas de encoding no Windows onde
            # r.json() pode lançar UnicodeDecodeError ou JSONDecodeError fora do ValueError.
            raw_bytes = r.content
            try:
                text = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text = raw_bytes.decode("latin-1")

            try:
                res_data = _json.loads(text)
                if isinstance(res_data, list) and len(res_data) == 0:
                    res_data = {
                        "format": "empty_stable",
                        "mensagem": "Handshake estabelecido. O setor espacial consultado encontra-se em estabilidade absoluta. Nenhuma anomalia ou evento registrado nos sensores da NASA."
                    }
            except (_json.JSONDecodeError, ValueError):
                # Resposta não é JSON (ex: XML do GIBS/Trek) — sanitiza para ASCII puro
                safe_preview = text[:3000].encode("ascii", errors="replace").decode("ascii")
                res_data = {"format": "xml_raw", "preview": safe_preview + "\n...[TRUNCATED]"}

            _cache_set(cache_key, res_data)
            return res_data

        except (httpx.TimeoutException, httpx.NetworkError) as e:
            # Caso ocorra falha de conexão física ou timeout nas tentativas iniciais
            if tentativa < max_retries - 1:
                await asyncio.sleep(0.5 * (tentativa + 1))
                continue
            
            return {
                "status": "error_detalhado",
                "codigo": 504,
                "titulo": "TEMPO LIMITE EXCEDIDO (504 TIMEOUT)",
                "mensagem": "Os servidores externos demoraram muito para responder ao nosso chamado e a conexão caiu.",
                "solucao": "A rede espacial pode estar congestionada. Refaça a operação em alguns segundos."
            }

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code

            # Se for um erro temporário retentável que persistiu até a última tentativa, ou erros permanentes (ex: 404, 403)
            detalhes_erros = {
                400: {
                    "titulo": "SINTAXE INCORRETA (400 BAD REQUEST)",
                    "mensagem": "O comando de transmissão enviado possui parâmetros não reconhecidos ou inválidos.",
                    "solucao": "Verifique o formato do texto inserido (ex: datas precisam ser AAAA-MM-DD, e códigos orbitais precisam ser números inteiros)."
                },
                403: {
                    "titulo": "ACESSO NEGADO / BLOQUEIO DE SEGURANÇA (403 FORBIDDEN)",
                    "mensagem": "O servidor remoto recusou a nossa conexão segura de rede para puxar os dados.",
                    "solucao": "Isso costuma ocorrer se o servidor externo suspeitar de tráfego robótico ou se a chave APIKey da NASA estiver inválida/expirada."
                },
                404: {
                    "titulo": "REGISTRO INEXISTENTE / ARQUIVADO (404 NOT FOUND)",
                    "mensagem": "A base de dados consultada realizou a varredura, mas não localizou nenhum dado correspondente.",
                    "solucao": "Verifique a ortografia do termo em inglês ou selecione outra data. APIs antigas também podem ter sido desativadas permanentemente pela NASA."
                },
                429: {
                    "titulo": "EXCESSO DE REQUISIÇÕES (429 RATE LIMIT)",
                    "mensagem": "Sua chave de acesso atingiu o teto limite de consultas permitidas por hora.",
                    "solucao": "Aguarde alguns minutos para que o sistema de banda da NASA reinicie, ou altere a sua API_KEY no arquivo de configuração."
                },
                500: {
                    "titulo": "FALHA NO SERVIDOR REMOTO (500 INTERNAL SERVER ERROR)",
                    "mensagem": "O servidor da agência espacial apresentou uma instabilidade de processamento ou erro interno.",
                    "solucao": "Não há erro no seu computador ou no nosso Gateway. O sistema da NASA está em manutenção. Tente novamente em instantes."
                },
                503: {
                    "titulo": "SERVIÇO INDISPONÍVEL (503 SERVICE UNAVAILABLE)",
                    "mensagem": "O servidor remoto da NASA não conseguiu responder à requisição após múltiplas tentativas.",
                    "solucao": "Isso costuma ocorrer em picos de tráfego ou durante manutenções curtas nos serviços centrais de imagem. Aguarde um instante e tente novamente."
                }
            }

            info = detalhes_erros.get(status_code, {
                "titulo": f"ANOMALIA DE RESPOSTA {status_code}",
                "mensagem": "Ocorreu um erro incomum no processamento da API.",
                "solucao": "Consulte o console do servidor para verificar os logs de conexão."
            })

            return {
                "status": "error_detalhado",
                "codigo": status_code,
                "titulo": info["titulo"],
                "mensagem": info["mensagem"],
                "solucao": info["solucao"],
                "raw_detail": e.response.text[:150]
            }

        except Exception as e:
            if tentativa < max_retries - 1:
                await asyncio.sleep(0.5 * (tentativa + 1))
                continue
            return {
                "status": "error_detalhado",
                "codigo": 500,
                "titulo": "FALHA INTERNA DO GATEWAY",
                "mensagem": f"Ocorreu uma falha inesperada na conexão local. Detalhes técnicos: {str(e)}",
                "solucao": "Verifique se a sua conexão com a internet está ativa e tente novamente."
            }


def hoje():   return str(date.today())
def atras(n): return str(date.today() - timedelta(days=n))


# ─── ROTAS DO GATEWAY ───

@app.get("/")
async def root():
    return {
        "status": "🟢 online",
        "projeto": "NASA Omni-Gateway",
        "equipe": ["Nícolas", "Tiago", "Jhonatan"],
        "instituicao": "UniCV 2026"
    }

# 1. APOD
@app.get("/apod")
async def apod(date: Optional[str] = Query(None)):
    return await _get(
        "https://api.nasa.gov/planetary/apod",
        {"date": date or hoje()},
        perfil="rapido",
    )

# 2. NeoWs (Asteroides)
@app.get("/neows/feed")
async def neows_feed(start_date: Optional[str] = Query(None)):
    return await _get(
        "https://api.nasa.gov/neo/rest/v1/feed",
        {"start_date": start_date or hoje(), "end_date": start_date or hoje()},
        perfil="rapido",
    )

# 3. DONKI
@app.get("/donki/gst")
async def donki_gst():
    return await _get(
        "https://api.nasa.gov/DONKI/GST",
        {"startDate": atras(30), "endDate": hoje()},
        perfil="rapido",
    )

# 4. EONET
@app.get("/eonet/events")
async def eonet_events():
    return await _get(
        "https://eonet.gsfc.nasa.gov/api/v3/events",
        {"status": "open", "limit": 12},
        key=False,
        perfil="rapido",
    )

# 5. EPIC
@app.get("/epic/natural")
async def epic_natural():
    return await _get(
        "https://api.nasa.gov/EPIC/api/natural",
        perfil="rapido",
    )

# 6. EXOPLANET (Sintaxe ADQL com SELECT TOP corrigida para evitar quebras)
@app.get("/exoplanet/planets")
async def exoplanet():
    q = "select top 15 pl_name,hostname,pl_orbper,disc_year,discoverymethod from ps where default_flag=1 order by disc_year desc"
    try:
        return await _get(
            "https://exoplanetarchive.ipac.caltech.edu/TAP/sync",
            {"query": q, "format": "json"},
            key=False,
            perfil="lento",
        )
    except Exception:
        return [
            {"pl_name": "Kepler-186f",        "hostname": "Kepler-186",       "pl_orbper": 129.94, "disc_year": 2014, "discoverymethod": "Transit"},
            {"pl_name": "Proxima Centauri b",  "hostname": "Proxima Centauri", "pl_orbper": 11.18,  "disc_year": 2016, "discoverymethod": "Radial Velocity"},
            {"pl_name": "TRAPPIST-1 d",        "hostname": "TRAPPIST-1",       "pl_orbper": 4.05,   "disc_year": 2016, "discoverymethod": "Transit"},
            {"pl_name": "TOI-700 d",           "hostname": "TOI-700",          "pl_orbper": 37.42,  "disc_year": 2020, "discoverymethod": "Transit"},
        ]

# 7. GIBS (Capabilities)
@app.get("/gibs/capabilities")
async def gibs():
    return await _get(
        "https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/wmts.cgi",
        {"SERVICE": "WMTS", "REQUEST": "GetCapabilities", "VERSION": "1.0.0"},
        key=False,
        perfil="lento",
    )

# 8. InSight (Clima de Marte — offline, retorno estático imediato)
@app.get("/insight")
async def insight():
    return {
        "status": "offline_preservado",
        "missao": "InSight Mars Lander",
        "coordenadas": "Elysium Planitia, Marte",
        "mensagem": "Uplink inativo. Sonda InSight silenciada em Marte em Dezembro de 2022 devido ao acúmulo de poeira nos painéis solares. Retornando telemetria climática de contingência preservada pela equipe:",
        "payload": {
            "sol": "1211",
            "data_terrestre": "2022-05-18",
            "sensor_temperatura": {"maxima": "-18.5 °C", "minima": "-81.2 °C", "media": "-54.8 °C"},
            "sensor_pressao": "685.4 Pa (Estável)",
            "sensor_vento": {"velocidade_maxima": "18.2 m/s", "direcao_predominante": "WNW (Oeste-Noroeste)"}
        }
    }

# 9. NASA Library
@app.get("/library/search")
async def library_search(q: str = Query("space")):
    return await _get(
        "https://images-api.nasa.gov/search",
        {"q": q, "media_type": "image"},
        key=False,
        perfil="padrao",
    )

# 10. OSDR (Ciência Aberta)
@app.get("/osdr/search")
async def osdr_search(term: str = Query("space")):
    return await _get(
        "https://osdr.nasa.gov/osdr/data/search",
        {"term": term, "type": "cgene", "size": 10},
        key=False,
        perfil="lento",
    )

# 11. SSC
@app.get("/ssc/observatories")
async def ssc_observatories():
    return await _get(
        "https://sscweb.gsfc.nasa.gov/WS/sscr/2/observatories",
        headers={"Accept": "application/json"},
        key=False,
        perfil="padrao",
    )

# 12. SSD (Meteoros)
@app.get("/ssd/fireball")
async def ssd_fireball():
    return await _get(
        "https://ssd-api.jpl.nasa.gov/fireball.api",
        {"limit": 15},
        key=False,
        perfil="rapido",
    )

# 13. TechPort
@app.get("/techport/projects")
async def techport_projects():
    return await _get(
        "https://api.nasa.gov/techport/api/projects",
        perfil="padrao",
    )

# 14. TechTransfer (Patentes)
@app.get("/techtransfer/patent")
async def tech_transfer(q: str = Query("engine")):
    url = f"https://technology.nasa.gov/api/api/patent/{q}"
    return await _get(url, key=False, perfil="padrao")

# 15. TLE (Satélites)
@app.get("/tle/search")
async def tle_search(search: str = Query("ISS")):
    return await _get(
        "https://tle.ivanstanojevic.me/api/tle",
        {"search": search},
        key=False,
        perfil="rapido",
    )

# 16. Trek WMTS
@app.get("/trek/moon")
async def trek_moon():
    return await _get(
        "https://trek.nasa.gov/tiles/Moon/EQ/LRO_WAC_Mosaic_Global_303ppd_v02/1.0.0/WMTSCapabilities.xml",
        key=False,
        perfil="lento",
    )

# BÔNUS: Mars Rover Photos (offline, retorno estático imediato)
@app.get("/mars/curiosity/photos")
async def mars_photos():
    return {
        "status": "offline_preservado",
        "missao": "Mars Rover Curiosity",
        "mensagem": "Uplink inativo. A API do Mars Rover foi arquivada e desativada oficialmente pela NASA em sua última atualização. Retornando telemetria e imagens reais de contingência:",
        "payload": {
            "sol": 1000,
            "rover": "Curiosity",
            "photos": [
                {
                    "id": 102693,
                    "sol": 1000,
                    "earth_date": "2015-05-30",
                    "img_src": "https://mars.nasa.gov/msl-raw-images/msss/01000/mcam/1000MR0044631300503690E01_DXXX.jpg",
                    "camera": {"name": "MAST", "full_name": "Mast Camera"}
                },
                {
                    "id": 102694,
                    "sol": 1000,
                    "earth_date": "2015-05-30",
                    "img_src": "https://mars.nasa.gov/msl-raw-images/msss/01000/mcam/1000ML0044631270405116E01_DXXX.jpg",
                    "camera": {"name": "MAST", "full_name": "Mast Camera"}
                },
                {
                    "id": 102695,
                    "sol": 1000,
                    "earth_date": "2015-05-30",
                    "img_src": "https://mars.nasa.gov/msl-raw-images/msss/01000/mcam/1000MR0044631200503680E01_DXXX.jpg",
                    "camera": {"name": "MAST", "full_name": "Mast Camera"}
                }
            ]
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)