"""
routers/core.py
───────────────────────────────────────────────────────────────────
Motor HTTP assíncrono compartilhado entre todos os routers.
Inclui: cache TTL, connection pooling, retry e tratamento de erros.
"""

import asyncio
import time
import json as _json
import httpx

API_KEY = "uU0HtIuSrObhlCycbYJGo2NhSph7mBOVnj8j05Jc"

# ── TIMEOUTS POR PERFIL ───────────────────────────────────────────
TIMEOUTS = {
    "padrao": 25.0,
    "rapido": 20.0,
    "lento":  40.0,
}

# ── HEADERS SIMULANDO NAVEGADOR ───────────────────────────────────
BROWSER_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
}

# ── CACHE EM MEMÓRIA COM TTL ──────────────────────────────────────
_TTL_MAP = {
    "apod":            300,
    "neo":             120,
    "DONKI":           180,
    "eonet":           120,
    "EPIC":            300,
    "exoplanet":      3600,
    "gibs":           3600,
    "fireball":        600,
    "techport":        600,
    "technology.nasa": 600,
    "ivanstanojevic":   60,
    "trek.nasa":      3600,
    "images-api":      300,
    "osdr":            300,
}

_cache: dict[str, tuple[float, object]] = {}


def ttl_para(url: str) -> int:
    for fragmento, ttl in _TTL_MAP.items():
        if fragmento in url:
            return ttl
    return 60


def cache_key(url: str, params: dict) -> str:
    return url + "|" + "&".join(f"{k}={v}" for k, v in sorted((params or {}).items()))


def cache_get(key: str, ttl: int):
    entry = _cache.get(key)
    if entry and (time.monotonic() - entry[0]) < ttl:
        return entry[1]
    return None


def cache_set(key: str, value):
    _cache[key] = (time.monotonic(), value)


# ── CLIENTES HTTP GLOBAIS (inicializados no lifespan) ─────────────
clients: dict[str, httpx.AsyncClient] = {}


# ── MOTOR HTTP PRINCIPAL ──────────────────────────────────────────
async def get(
    url: str,
    params: dict = None,
    key: bool = True,
    headers: dict = None,
    perfil: str = "padrao",
):
    """
    Realiza GET assíncrono com:
    - injeção automática de api_key
    - cache TTL por URL
    - retry em erros 502/503/504
    - respostas de erro estruturadas em JSON
    """
    p = dict(params or {})
    h = dict(headers or {})
    if key:
        p["api_key"] = API_KEY

    ck = cache_key(url, p)
    ttl = ttl_para(url)
    cached = cache_get(ck, ttl)
    if cached is not None:
        return cached

    client = clients.get(perfil) or clients.get("padrao") or httpx.AsyncClient(
        timeout=TIMEOUTS["padrao"], follow_redirects=True, verify=False, headers=BROWSER_HEADERS
    )

    max_retries = 3
    for tentativa in range(max_retries):
        try:
            r = await client.get(url, params=p, headers=h)

            if r.status_code in (502, 503, 504) and tentativa < max_retries - 1:
                await asyncio.sleep(0.5 * (tentativa + 1))
                continue

            r.raise_for_status()

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
                safe_preview = text[:3000].encode("ascii", errors="replace").decode("ascii")
                res_data = {"format": "xml_raw", "preview": safe_preview + "\n...[TRUNCATED]"}

            cache_set(ck, res_data)
            return res_data

        except (httpx.TimeoutException, httpx.NetworkError):
            if tentativa < max_retries - 1:
                await asyncio.sleep(0.5 * (tentativa + 1))
                continue
            return _erro(504, "TEMPO LIMITE EXCEDIDO (504 TIMEOUT)",
                         "Os servidores externos demoraram muito para responder.",
                         "Refaça a operação em alguns segundos.")

        except httpx.HTTPStatusError as e:
            sc = e.response.status_code
            mapa = {
                400: ("SINTAXE INCORRETA (400 BAD REQUEST)",
                      "Parâmetros inválidos na requisição.",
                      "Verifique datas (AAAA-MM-DD) e tipos de parâmetros."),
                403: ("ACESSO NEGADO (403 FORBIDDEN)",
                      "O servidor remoto recusou a conexão.",
                      "Verifique se a API_KEY da NASA é válida."),
                404: ("REGISTRO INEXISTENTE (404 NOT FOUND)",
                      "Nenhum dado encontrado para esta consulta.",
                      "Verifique o termo ou selecione outra data."),
                429: ("RATE LIMIT EXCEDIDO (429)",
                      "Limite de requisições por hora atingido.",
                      "Aguarde alguns minutos e tente novamente."),
                500: ("FALHA NO SERVIDOR REMOTO (500)",
                      "O servidor da NASA apresentou instabilidade.",
                      "Não há erro local. Tente novamente em instantes."),
                503: ("SERVIÇO INDISPONÍVEL (503)",
                      "O servidor da NASA não respondeu após múltiplas tentativas.",
                      "Aguarde e tente novamente."),
            }
            titulo, msg, sol = mapa.get(sc, (f"ANOMALIA {sc}", "Erro inesperado.", "Verifique os logs."))
            return {**_erro(sc, titulo, msg, sol), "raw_detail": e.response.text[:150]}

        except Exception as e:
            if tentativa < max_retries - 1:
                await asyncio.sleep(0.5 * (tentativa + 1))
                continue
            return _erro(500, "FALHA INTERNA DO GATEWAY",
                         f"Erro inesperado: {str(e)}",
                         "Verifique a conexão com a internet.")


def _erro(codigo: int, titulo: str, mensagem: str, solucao: str) -> dict:
    return {
        "status": "error_detalhado",
        "codigo": codigo,
        "titulo": titulo,
        "mensagem": mensagem,
        "solucao": solucao,
    }
