# 🚀 NASA Omni-Gateway

**Trabalho Bimestral — Integração de APIs | UniCV 2026**

> Gateway FastAPI que intermedia 100% das requisições entre o painel web e os servidores oficiais da NASA. Nenhuma chamada direta ao domínio `api.nasa.gov` é realizada pelo navegador do usuário.

**Equipe:** Nícolas · Tiago · Jhonatan

---

## Sumário

- [Visão Geral da Arquitetura](#visão-geral-da-arquitetura)
- [Pré-requisitos](#pré-requisitos)
- [Instalação](#instalação)
- [Como Rodar](#como-rodar)
- [Endpoints Disponíveis](#endpoints-disponíveis)
- [Recursos Técnicos](#recursos-técnicos)
- [Estrutura de Arquivos](#estrutura-de-arquivos)
- [Tratamento de Erros](#tratamento-de-erros)

---

## Visão Geral da Arquitetura

```
Navegador (index.html)
        │
        │  HTTP GET → localhost:8000
        ▼
┌─────────────────────────┐
│   FastAPI Back-end      │  ← main.py
│   (NASA Omni-Gateway)   │
│                         │
│  • Cache TTL por rota   │
│  • Retry automático     │
│  • Tratamento de erros  │
└─────────────────────────┘
        │
        │  HTTPS → api.nasa.gov / outros
        ▼
   APIs Oficiais da NASA
```

O front-end **nunca** acessa a NASA diretamente. Toda comunicação passa pelo back-end FastAPI, que centraliza o tratamento de erros, cache e timeouts.

---

## Pré-requisitos

- Python 3.10 ou superior
- pip

---

## Instalação

```bash
# 1. Clone ou baixe o projeto
# 2. Instale as dependências
pip install -r requirements.txt
```

---

## Como Rodar

```bash
# Opção 1 — Recomendado (evita problemas de PATH no Windows)
python -m uvicorn main:app --reload

# Opção 2
uvicorn main:app --reload
```

O servidor sobe em: **http://localhost:8000**

Documentação interativa Swagger: **http://localhost:8000/docs**

Depois de subir o servidor, abra o arquivo `index.html` diretamente no navegador.

---

## Endpoints Disponíveis

| # | Rota FastAPI | Fonte NASA | Descrição |
|---|---|---|---|
| 1 | `GET /apod` | APOD | Astronomy Picture of the Day. Parâmetro: `?date=AAAA-MM-DD` |
| 2 | `GET /neows/feed` | NeoWs | Asteroides próximos à Terra hoje. Parâmetro: `?start_date=AAAA-MM-DD` |
| 3 | `GET /donki/gst` | DONKI | Tempestades geomagnéticas dos últimos 30 dias |
| 4 | `GET /eonet/events` | EONET | Eventos naturais abertos (vulcões, tempestades, icebergs) |
| 5 | `GET /epic/natural` | EPIC | Imagens do planeta Terra pelo satélite DSCOVR |
| 6 | `GET /exoplanet/planets` | Exoplanet Archive | 15 exoplanetas mais recentes do arquivo Kepler |
| 7 | `GET /gibs/capabilities` | GIBS WMTS | Capabilities XML do serviço de imagens globais |
| 8 | `GET /insight` | InSight (offline) | Telemetria climática marciana de contingência |
| 9 | `GET /library/search` | NASA Image Library | Busca no acervo de mídia. Parâmetro: `?q=termo` |
| 10 | `GET /osdr/search` | OSDR | Repositório de ciência aberta espacial. Parâmetro: `?term=termo` |
| 11 | `GET /ssc/observatories` | SSC | Lista de observatórios satelitais |
| 12 | `GET /ssd/fireball` | SSD/CNEOS | Registro de impactos atmosféricos de meteoros |
| 13 | `GET /techport/projects` | TechPort | Projetos de tecnologia espacial em desenvolvimento |
| 14 | `GET /techtransfer/patent` | TechTransfer | Patentes da NASA. Parâmetro: `?q=termo` |
| 15 | `GET /tle/search` | TLE API | Rastreamento orbital de satélites. Parâmetro: `?search=nome` |
| 16 | `GET /trek/moon` | Trek WMTS | Capabilities do mapeamento lunar |
| 17 | `GET /mars/curiosity/photos` | Mars Rover (offline) | Fotos históricas do rover Curiosity |

---

## Recursos Técnicos

### Cache TTL por Rota
Cada categoria de endpoint possui um tempo de vida de cache adequado à frequência de atualização dos dados:

| Rota | TTL |
|---|---|
| APOD, EPIC | 5 minutos |
| NeoWs, EONET | 2 minutos |
| DONKI | 3 minutos |
| Exoplanet, GIBS, Trek | 1 hora |
| TLE | 1 minuto (muda com frequência) |

### Retry Automático
Erros temporários `502`, `503` e `504` disparam até 3 tentativas automáticas com espera incremental (0.5s, 1.0s) antes de retornar erro ao cliente.

### Timeouts Individuais
Três perfis de timeout para evitar que rotas lentas (XML pesado, TAP lento) bloqueiem o servidor:

- **Rápido:** 20s — APOD, NeoWs, DONKI, TLE
- **Padrão:** 25s — Library, SSC, TechPort, TechTransfer
- **Lento:** 40s — GIBS, Trek, Exoplanet, OSDR

### Connection Pooling
Clientes `httpx.AsyncClient` são criados uma única vez no startup via `lifespan` e reutilizados em todas as requisições, reduzindo overhead de conexão TCP.

### Endpoints Offline com Dados de Contingência
A sonda **InSight** (encerrada em Dez/2022) e a **API do Mars Rover** (descontinuada pela NASA) retornam dados históricos reais preservados diretamente no gateway, sem depender de servidores externos.

---

## Estrutura de Arquivos

```
nasa-omni-gateway/
├── main.py            # Back-end FastAPI — gateway completo
├── index.html         # Front-end — painel visual de controle
├── requirements.txt   # Dependências Python
└── README.md          # Esta documentação
```

---

## Tratamento de Erros

O gateway nunca expõe um erro HTTP bruto ao front-end. Todos os erros são convertidos em objetos JSON estruturados com três campos:

```json
{
  "status": "error_detalhado",
  "titulo": "REGISTRO INEXISTENTE / ARQUIVADO (404 NOT FOUND)",
  "mensagem": "Descrição legível do problema.",
  "solucao": "Instrução de como resolver."
}
```

Erros cobertos: `400`, `403`, `404`, `429`, `500`, `502`, `503`, `504`, timeout de rede e falhas de encoding UTF-8/Latin-1.

---

## Uso de IA (Vibe Coding)

Este projeto foi desenvolvido com auxílio de **Claude (Anthropic)** para:
- Geração e refinamento do código FastAPI (`main.py`)
- Estrutura do front-end (`index.html`)
- Estratégias de cache, retry e tratamento de erros
- Documentação (este README)

O uso de ferramentas de IA foi parte intencional do processo de desenvolvimento, conforme previsto nos critérios de avaliação da disciplina.
