# DocRef Dashboard — Panel de Auditoría Clínica

Sistema multi-usuario para revisar y validar interconsultas médicas. Cada auditor trabaja en su propia sesión, con bloqueo optimista de registros para evitar ediciones simultáneas.

---

## Índice

1. [Arquitectura](#1-arquitectura)
2. [Estructura de carpetas](#2-estructura-de-carpetas)
3. [Inicio rápido (desarrollo local)](#3-inicio-rápido-desarrollo-local)
4. [Servicio API](#4-servicio-api)
5. [Servicio Frontend](#5-servicio-frontend)
6. [Sistema de sesiones y bloqueo de registros](#6-sistema-de-sesiones-y-bloqueo-de-registros)
7. [Paginación](#7-paginación)
8. [Datos](#8-datos)
9. [Endpoints de la API](#9-endpoints-de-la-api)
10. [Variables de entorno](#10-variables-de-entorno)
11. [Despliegue en producción](#11-despliegue-en-producción)

---

## 1. Arquitectura

```
                        Internet / Red local
                               │
                               ▼ :80
                    ┌─────────────────────┐
                    │        nginx        │  reverse proxy
                    │   (nginx:1.27-alpine│  WebSocket pass-through
                    └──────┬──────────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
              ▼                         ▼
   ┌─────────────────┐       ┌─────────────────┐
   │    frontend      │  HTTP │      api        │
   │  Streamlit 1.x  │──────▶│   FastAPI 0.11  │
   │  Python 3.11    │       │   Python 3.11   │
   │  :8501 (interno)│       │  :8000 (interno)│
   └─────────────────┘       └────────┬────────┘
                                      │ psycopg2
                                      ▼
                             ┌─────────────────┐
                             │   PostgreSQL 16  │
                             │  volumen pg_data │
                             └─────────────────┘
```

- **nginx** es el único punto de entrada público (puerto 80 / 443).
- **frontend** llama a la **api** dentro de la red Docker (`http://api:8000`).
- **api** lee los archivos JSON de `data/` (solo lectura) y persiste decisiones en **PostgreSQL**.
- La base de datos sobrevive reinicios gracias al volumen `pg_data`.

---

## 2. Estructura de carpetas

```
streamlitssasur/
│
├── api/
│   ├── main.py              # FastAPI: endpoints, seed, claims, paginación
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── app.py               # Streamlit: UI, sesiones, paginación, auditoría
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .streamlit/
│       └── config.toml      # Tema visual
│
├── nginx/
│   └── nginx.conf           # Reverse proxy con soporte WebSocket
│
├── data/                    # Archivos JSON de interconsultas (semilla)
│   └── *.json
│
├── docker-compose.yml       # Orquestación: db, api, frontend, nginx
├── .env.example             # Plantilla de variables de entorno
├── deploy.sh                # Script de despliegue para VM
├── app.py                   # Versión standalone (sin Docker, sin API)
└── README.md
```

---

## 3. Inicio rápido (desarrollo local)

```bash
# Clonar el repositorio
git clone <repo-url> && cd streamlitssasur

# Copiar datos de interconsultas a data/
cp /ruta/a/tus/datos/*.json data/

# Levantar todos los servicios
docker compose up --build

# Acceso:
#   Panel:  http://localhost       (vía nginx)
#   API:    http://localhost/docs  (Swagger UI)
#
# Acceso directo sin nginx (solo desarrollo):
#   Panel:  http://localhost:8501
#   API:    http://localhost:8000/docs
```

Para parar:
```bash
docker compose down        # conserva la base de datos
docker compose down -v     # borra también la DB (datos de auditoría)
```

---

## 4. Servicio API

**Stack:** Python 3.11 · FastAPI · Uvicorn · psycopg2 · PostgreSQL 16

### Esquema de base de datos

```sql
-- Tabla principal: una fila por interconsulta
CREATE TABLE interconsultas (
    id                BIGSERIAL PRIMARY KEY,
    fuente            TEXT      NOT NULL,           -- stem del archivo JSON
    num_interconsulta TEXT,                         -- clave de negocio
    validado          BOOLEAN   DEFAULT NULL,       -- TRUE/FALSE/NULL
    nota_auditoria    TEXT      NOT NULL DEFAULT '',
    record            JSONB     NOT NULL            -- objeto completo
);

-- Tabla de labels (compatibilidad)
CREATE TABLE labels (
    key     TEXT PRIMARY KEY,
    status  TEXT NOT NULL CHECK (status IN ('valid', 'invalid')),
    note    TEXT NOT NULL DEFAULT ''
);

-- Tabla de bloqueo de registros en revisión
CREATE TABLE claims (
    key        TEXT PRIMARY KEY,
    auditor    TEXT NOT NULL,
    claimed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Semilla automática

Al arrancar, si `interconsultas` está vacía, la API lee todos los `*.json` de `DATA_DIR` y los inserta. Cada archivo genera una `fuente` (nombre sin extensión). Cuando la tabla ya tiene datos, la semilla se omite.

### `api/Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 5. Servicio Frontend

**Stack:** Python 3.11 · Streamlit ≥ 1.28 · requests

### Flujo de ejecución

```
main()
 ├─ fetch_files()              → GET /api/files  (caché 5 min)
 ├─ ensure_session_defaults()  → genera Auditor-XXXX, carga labels locales
 ├─ fetch_claims()             → GET /api/claims (caché 10 s)
 ├─ Sidebar: selectbox fuente, bandeja, filtros, paginación
 ├─ fetch_records(fuente, page)→ GET /api/records/{fuente}?page=N (caché 60 s)
 ├─ filter_records(...)        → filtrado en memoria Python
 ├─ api_claim(active_key)      → POST /api/claims/{key}
 ├─ Topbar + layout principal
 └─ @st.fragment(run_every=20) → heartbeat + indicador de auditores activos
```

### Funciones auxiliares clave

| Función | Qué hace |
|---------|----------|
| `fuente_display(fuente)` | Convierte stem del JSON en nombre legible: `interconsultas_mg_cirugia_adulto_1000` → `Cirugia Adulto` |
| `record_key(row, fallback)` | Clave única del registro: `NUM_INTERCONSULTA` → `ID` → índice |
| `row_status(row, key, labels)` | Estado real: usa `_validado` de la API con fallback a `labels` local |
| `filter_records(...)` | Filtra por búsqueda libre, bandeja, prioridad |
| `count_by_status(...)` | Contadores para los badges del sidebar |

---

## 6. Sistema de sesiones y bloqueo de registros

Cada pestaña de navegador recibe un identificador único (`Auditor-XXXX`). Al abrir un registro, la sesión lo "reclama" para evitar que otro auditor edite el mismo folio simultáneamente.

### Ciclo de vida de un claim

```
Abrir pestaña
    → genera Auditor-XXXX (session_state, vive mientras el tab está abierto)

Seleccionar registro
    → POST /api/claims/{key}?auditor=Auditor-XXXX
    → si otro auditor lo tiene Y está activo → 409 → saltar al siguiente libre

Mientras la pestaña esté abierta
    → @st.fragment(run_every=20): POST /api/claims/{key}/heartbeat cada 20s

Cerrar pestaña
    → websocket de Streamlit se corta → fragment deja de correr
    → claim deja de renovarse → envejece

A los 45s sin heartbeat
    → claim se considera "obsoleto" → override automático permitido
    → nueva sesión puede tomar el registro sin esperar los 2 min de TTL
```

### Parámetros configurables (en `api/main.py`)

| Constante | Valor | Significado |
|-----------|-------|-------------|
| `CLAIM_TTL_MINUTES` | `2` | Tiempo máximo de vida de un claim sin renovación |
| `STALE_CLAIM_SECONDS` | `45` | Segundos sin heartbeat para considerar el claim obsoleto y permitir override |

---

## 7. Paginación

La API devuelve los registros en páginas para evitar cargar miles de filas de una vez.

### Endpoint

```
GET /api/records/{fuente}?page=1&page_size=50
```

**Respuesta:**
```json
{
  "total": 1000,
  "page": 1,
  "page_size": 50,
  "records": [ { ...registro... }, ... ]
}
```

### Frontend

- `PAGE_SIZE = 50` registros por página (configurable en `frontend/app.py`).
- El sidebar muestra `PÁGINA X / Y (N registros)` con botones **← Anterior** y **Siguiente →**.
- Al cambiar de fuente o página se resetea la selección y se libera el claim activo.
- Los filtros (bandeja, prioridad, búsqueda) se aplican sobre los registros de la página actual.

---

## 8. Datos

### Formato JSON

Cada archivo en `data/` debe ser un array JSON de objetos. El stem del nombre de archivo se usa como identificador de fuente:

```
data/interconsultas_mg_cirugia_adulto_1000.json  →  fuente: "interconsultas_mg_cirugia_adulto_1000"
                                                    display: "Cirugia Adulto"
```

**Estructura mínima de cada objeto:**

```json
{
  "NUM_INTERCONSULTA": 212616149,
  "NOM_DIAGNOSTICO": "VICIO REFRACCION PRESBICIA",
  "HISTORIA_CLINICA": "Texto del relato clínico..."
}
```

### Campos usados por la UI

| Campo | Dónde aparece |
|-------|---------------|
| `NUM_INTERCONSULTA` | Folio, clave de auditoría |
| `NOM_DIAGNOSTICO` | Tarjeta y detalle |
| `COD_DIAGNO` | Badge CIE-10 |
| `HISTORIA_CLINICA` | Textarea de solo lectura |
| `EXAMENES_COMPLEMENTARIOS` | Sección de exámenes |
| `ESTABLECIMIENTO_ORIGEN/DESTINO` | Panel de origen/destino |
| `ESPECIALIDAD_ORIGEN/DESTINO` | Panel de origen/destino |
| `FECHA_IC` | Tarjeta y footer |
| `PRIORIDAD_DESTINO` | Filtro y badge de prioridad |
| `ESTADO_AUGE` + `PROBLEMA_SALUD` | Badge GES/AUGE |
| `PREVISION_IC` | Panel paciente |
| `EDAD_AÑOS` | Panel paciente |
| `MOTIVO_INTERCONSULTA` | Panel requerimientos |
| `SE_REQUIERE` | Panel requerimientos |
| `DERIVADO_PARA` | Panel requerimientos |
| `TIPO_DERIVACION` | Panel origen |
| `POLICLINICO_DESTINO` | Panel destino |
| `GESTION_INTERCONSULTA` | Footer |

### Agregar nuevos datos

```bash
# Mientras Docker está corriendo:
cp nuevos_datos.json data/

# La API los detecta automáticamente solo si la DB está vacía.
# Si la DB ya tiene datos, se requiere un re-seed completo:
docker compose down -v
docker compose up -d
```

---

## 9. Endpoints de la API

Documentación interactiva: **http://localhost/docs** (Swagger UI)

### Registros

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/health` | Health check: `{"status": "ok"}` |
| `GET` | `/api/files` | Lista de fuentes disponibles |
| `GET` | `/api/records/{fuente}?page=1&page_size=50` | Registros paginados de una fuente |

### Auditoría

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/api/labels` | Todas las validaciones guardadas |
| `PUT` | `/api/labels/{key}` | Crear/actualizar validación `{status, note}` |
| `DELETE` | `/api/labels/{key}` | Revertir a pendiente |
| `GET` | `/api/export` | Exportar todas las auditadas |
| `GET` | `/api/export/{fuente}` | Exportar auditadas de una fuente |
| `GET` | `/api/export-stats` | Contadores por fuente |

### Sesiones (claims)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/api/claims` | Claims activos: `{key: auditor}` |
| `POST` | `/api/claims/{key}?auditor=X` | Reclamar registro |
| `DELETE` | `/api/claims/{key}` | Liberar claim |
| `POST` | `/api/claims/{key}/release` | Liberar claim (vía POST, para sendBeacon) |
| `POST` | `/api/claims/{key}/heartbeat?auditor=X` | Renovar claim activo |

---

## 10. Variables de entorno

### Servicio `api`

| Variable | Default | Descripción |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://interconsultas:interconsultas@db:5432/interconsultas` | Conexión a PostgreSQL |
| `DATA_DIR` | `/data` | Carpeta con archivos JSON de semilla |

### Servicio `frontend`

| Variable | Default | Descripción |
|----------|---------|-------------|
| `API_URL` | `http://localhost:8000` | URL de la API (interna Docker: `http://api:8000`) |

### Servicio `db`

| Variable | Default | Descripción |
|----------|---------|-------------|
| `POSTGRES_USER` | `interconsultas` | Usuario de la DB |
| `POSTGRES_PASSWORD` | `interconsultas` | Contraseña (cambiar en producción) |
| `POSTGRES_DB` | `interconsultas` | Nombre de la base de datos |

Todas las variables con defaults de producción se controlan desde `.env` (ver `.env.example`).

---

## 11. Despliegue en producción

Ver [DEPLOY.md](DEPLOY.md) para instrucciones detalladas de despliegue en VM con nginx, SSL y mantenimiento.

```bash
# Resumen de despliegue en VM
git clone <repo> && cd streamlitssasur
cp .env.example .env && nano .env   # editar contraseñas
cp /ruta/datos/*.json data/
bash deploy.sh
```
