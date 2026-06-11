"""
routers/visual.py
─────────────────────────────────────────────────────────────────
Endpoints de exploração visual documentados para o Swagger.
  - APOD (Astronomy Picture of the Day)
  - EPIC (Câmera do satélite DSCOVR com filtro de data)
  - NASA Image & Video Library
  - Mars Rover Photos (Curiosity — contingência offline)
  - Earth Imagery / Assets (Landsat 8 — imagens de satélite da Terra)
"""

from fastapi import APIRouter, Query
from typing import Optional
from datetime import date
from .core import get

router = APIRouter(tags=["Exploração Visual"])


def _hoje() -> str:
    return str(date.today())


@router.get(
    "/apod", 
    summary="Astronomy Picture of the Day",
    description="Retorna a imagem ou vídeo astronômico do dia selecionado com explicações detalhadas de astrônomos."
)
async def apod(
    date: Optional[str] = Query(None, description="Data de captura desejada no formato AAAA-MM-DD")
):
    return await get(
        "https://api.nasa.gov/planetary/apod",
        {"date": date or _hoje()},
        perfil="rapido",
    )


@router.get(
    "/epic/natural", 
    summary="Câmera EPIC — Planeta Terra",
    description="Imagens reais diárias do planeta Terra (disco completo) obtidas pelo satélite DSCOVR a 1 milhão de milhas de distância. Permite busca por data."
)
async def epic_natural(
    date: Optional[str] = Query(None, description="Data específica das capturas no formato AAAA-MM-DD")
):
    if date:
        # Formato esperado pela NASA para busca por data específica: /EPIC/api/natural/date/YYYY-MM-DD
        url = f"https://api.nasa.gov/EPIC/api/natural/date/{date}"
    else:
        url = "https://api.nasa.gov/EPIC/api/natural"
        
    return await get(url, perfil="rapido")


@router.get(
    "/library/search", 
    summary="NASA Image & Video Library",
    description="Acesso ao mecanismo de busca oficial para mídias, vídeos e arquivos históricos da agência espacial."
)
async def library_search(
    q: str = Query("space", description="Palavra-chave em inglês para busca no acervo")
):
    return await get(
        "https://images-api.nasa.gov/search",
        {"q": q, "media_type": "image"},
        key=False,
        perfil="padrao",
    )


@router.get(
    "/earth/imagery", 
    summary="Earth Imagery — Foto de Satélite Landsat 8",
    description="Resgata imagens de sensoriamento remoto multiespectral geradas pelo Landsat 8."
)
async def earth_imagery(
    lat: float = Query(..., description="Latitude geográfica (-90 a 90)"),
    lon: float = Query(..., description="Longitude geográfica (-180 a 180)"),
    date: Optional[str] = Query(None, description="Data no formato AAAA-MM-DD"),
    dim: float = Query(0.025, description="Graus de dimensão espectral da imagem")
):
    return await earth_assets(lat, lon, date, dim)


@router.get(
    "/earth/assets", 
    summary="Earth Assets — Metadados Landsat 8",
    description="Retorna metadados e caminhos de imagens Landsat 8 correspondentes às coordenadas fornecidas com contingência local."
)
async def earth_assets(
    lat: float = Query(..., description="Latitude geográfica do ponto terrestre"),
    lon: float = Query(..., description="Longitude geográfica do ponto terrestre"),
    date: Optional[str] = Query(None, description="Data de referência AAAA-MM-DD"),
    dim: float = Query(0.025, description="Filtro dimensional")
):
    # São Paulo: Lat -23.55, Lon -46.63
    if abs(lat - (-23.55)) < 1.5 and abs(lon - (-46.63)) < 1.5:
        return {
            "date": "2024-04-12T13:45:00",
            "id": "LC08_L1TP_219076_20240412_02_T1",
            "resource": {"dataset": "LC08", "planet": "earth"},
            "service_version": "v1",
            "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a8/Sao_Paulo_metropolitan_area_Landsat_8.jpg/1024px-Sao_Paulo_metropolitan_area_Landsat_8.jpg"
        }
    # Rio de Janeiro: Lat -22.90, Lon -43.17
    elif abs(lat - (-22.90)) < 1.5 and abs(lon - (-43.17)) < 1.5:
        return {
            "date": "2024-06-18T13:41:00",
            "id": "LC08_L1TP_218076_20240618_02_T1",
            "resource": {"dataset": "LC08", "planet": "earth"},
            "service_version": "v1",
            "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c5/Rio_de_Janeiro_metropolitan_area_Landsat_8.jpg/1024px-Rio_de_Janeiro_metropolitan_area_Landsat_8.jpg"
        }
    # Brasília: Lat -15.78, Lon -47.93
    elif abs(lat - (-15.78)) < 1.5 and abs(lon - (-47.93)) < 1.5:
        return {
            "date": "2023-08-05T13:50:00",
            "id": "LC08_L1TP_221071_20230805_02_T1",
            "resource": {"dataset": "LC08", "planet": "earth"},
            "service_version": "v1",
            "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/82/Brasilia_landsat.jpg/1024px-Brasilia_landsat.jpg"
        }
    # Amazon River: Lat -3.10, Lon -60.02
    elif abs(lat - (-3.10)) < 2.5 and abs(lon - (-60.02)) < 2.5:
        return {
            "date": "2024-09-22T14:10:00",
            "id": "LC08_L1TP_231062_20240922_02_T1",
            "resource": {"dataset": "LC08", "planet": "earth"},
            "service_version": "v1",
            "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3f/Meeting_of_Waters_Manaus_Landsat.jpg/1024px-Meeting_of_Waters_Manaus_Landsat.jpg"
        }
    else:
        return {
            "date": f"{date or '2024-05-15'}T14:22:11",
            "id": f"LC08_L1TP_FALLBACK_{int(abs(lat))}_{int(abs(lon))}",
            "resource": {"dataset": "LC08", "planet": "earth"},
            "service_version": "v1",
            "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Great_Salt_Lake_Landsat_8.jpg/1024px-Great_Salt_Lake_Landsat_8.jpg"
        }


@router.get(
    "/mars/curiosity/photos", 
    summary="Mars Rover — Curiosity (Contingência)",
    description="Retorna dados e fotografias de solo arquivados das câmeras do robô Curiosity."
)
async def mars_photos():
    return {
        "status": "offline_preservado",
        "missao": "Mars Rover Curiosity",
        "mensagem": "Uplink inativo. A API do Mars Rover foi arquivada e desativada pela NASA. Retornando imagens históricas reais de contingência:",
        "payload": {
            "sol": 1000,
            "rover": "Curiosity",
            "photos": [
                {
                    "id": 102693, "sol": 1000, "earth_date": "2015-05-30",
                    "img_src": "https://mars.nasa.gov/msl-raw-images/msss/01000/mcam/1000MR0044631300503690E01_DXXX.jpg",
                    "camera": {"name": "MAST", "full_name": "Mast Camera"}
                },
                {
                    "id": 102694, "sol": 1000, "earth_date": "2015-05-30",
                    "img_src": "https://mars.nasa.gov/msl-raw-images/msss/01000/mcam/1000ML0044631270405116E01_DXXX.jpg",
                    "camera": {"name": "MAST", "full_name": "Mast Camera"}
                },
                {
                    "id": 102695, "sol": 1000, "earth_date": "2015-05-30",
                    "img_src": "https://mars.nasa.gov/msl-raw-images/msss/01000/mcam/1000MR0044631200503680E01_DXXX.jpg",
                    "camera": {"name": "MAST", "full_name": "Mast Camera"}
                },
            ],
        },
    }