# DocRef Dashboard — Panel de Auditoría Clínica

Sistema para revisar y validar interconsultas médicas almacenadas en archivos
JSONL. Arquitectura monolítica en Docker con dos servicios Python.

---

## Índice

1. [Arquitectura general](#1-arquitectura-general)
2. [Estructura de carpetas](#2-estructura-de-carpetas)
3. [Cómo funciona el flujo completo](#3-cómo-funciona-el-flujo-completo)
4. [Servicio API (`api/`)](#4-servicio-api-api)
5. [Servicio Frontend (`frontend/`)](#5-servicio-frontend-frontend)
6. [Datos (`data/`)](#6-datos-data)
7. [Docker y despliegue](#7-docker-y-despliegue)
8. [Variables de entorno](#8-variables-de-entorno)
9. [Endpoints de la API](#9-endpoints-de-la-api)
10. [Persistencia y volúmenes](#10-persistencia-y-volúmenes)
11. [Desarrollo local sin Docker](#11-desarrollo-local-sin-docker)
12. [Agregar nuevos datos](#12-agregar-nuevos-datos)

---

## 1. Arquitectura general

```
                ┌─────────────────────────────────┐
                │        Docker Compose            │
                │                                  │
                │  ┌─────────────┐                 │
 Usuario        │  │  frontend   │  :8501           │
 (navegador) ───┼─▶│  Streamlit  │                 │
                │  │  Python 3.11│                 │
                │  └──────┬──────┘                 │
                │         │  HTTP (API_URL)         │
                │         ▼                         │
                │  ┌─────────────┐   /data (ro)    │
                │  │    api      │◀──────────────── ├── data/*.jsonl
                │  │  FastAPI    │  :8000           │
                │  │  Python 3.11│                  │
                │  └──────┬──────┘                 │
                │         │  SQLite                │
                │         ▼                         │
                │  ┌─────────────┐                 │
                │  │  labels_db  │  volumen Docker  │
                │  │  labels.db  │  (persistente)   │
                │  └─────────────┘                 │
                └─────────────────────────────────-┘
```

- **`api`** es el único servicio que toca el sistema de archivos.
  Lee los `.jsonl` en modo lectura y escribe las validaciones en SQLite.
- **`frontend`** no lee archivos locales. Todo lo obtiene llamando a la API.
- La carpeta `data/` se monta como volumen de solo lectura en `api`.
- Las validaciones (quién aprobó/rechazó qué registro, con qué nota)
  se guardan en `labels_db`, un volumen Docker que sobrevive reinicios.

---

## 2. Estructura de carpetas

```
streamlit_medicos/
│
├── frontend/                   # Servicio Streamlit
│   ├── app.py                  # Aplicación principal
│   ├── requirements.txt        # streamlit, requests
│   ├── Dockerfile
│   └── .streamlit/
│       └── config.toml         # Tema visual (colores, headless)
│
├── api/                        # Servicio FastAPI
│   ├── main.py                 # Toda la lógica de la API
│   ├── requirements.txt        # fastapi, uvicorn, pydantic
│   └── Dockerfile
│
├── data/                       # Carpeta de datos (semilla + lectura en vivo)
│   └── *.jsonl                 # Un archivo por especialidad médica
│
├── docker-compose.yml          # Orquestación de los dos servicios
├── app.py                      # Versión standalone (sin Docker, sin API)
└── README.md
```

---

## 3. Cómo funciona el flujo completo

### Arranque

1. `docker compose up --build` construye las dos imágenes.
2. Docker levanta primero `api` y espera hasta que su healthcheck responda
   `200 OK` en `/health`.
3. Solo cuando la API está sana, Docker levanta `frontend`.

### Ciclo de una sesión de usuario

```
Usuario abre http://localhost:8501
        │
        ▼
Streamlit ejecuta main()
        │
        ├─▶ GET /api/files          → lista de archivos .jsonl disponibles
        │
        ├─▶ GET /api/labels         → validaciones previas guardadas en SQLite
        │     (una sola vez por sesión de navegador, queda en session_state)
        │
        ├─▶ Usuario selecciona archivo
        │
        ▼
        GET /api/records/{filename} → lista de registros del JSONL
        (resultado cacheado 5 min en memoria de Streamlit)
        │
        ▼
        Streamlit renderiza la UI con los registros filtrados
        │
        ├─▶ Usuario hace clic en "Validar pertinencia"
        │     PUT /api/labels/{key}  body: {status:"valid", note:"..."}
        │     + actualiza session_state local (sin esperar re-fetch)
        │
        └─▶ Usuario hace clic en "Volver a pendiente"
              DELETE /api/labels/{key}
              + borra clave de session_state
```

### Estado de los labels: doble escritura

Los labels se mantienen en **dos lugares simultáneos**:

| Lugar | Qué guarda | Para qué sirve |
|---|---|---|
| `st.session_state` | `label_by_key = {key: "valid"\|"invalid"}` | Respuesta inmediata en UI sin esperar API |
| SQLite (`labels.db`) | Tabla `labels(key, status, note)` | Persistencia entre sesiones y reinicios |

Al abrir el navegador por primera vez, `ensure_session_defaults()` hace un
`GET /api/labels` y carga el estado guardado en `session_state`. Desde ese
momento la sesión es autónoma y solo llama a la API al escribir cambios.

---

## 4. Servicio API (`api/`)

**Tecnologías:** Python 3.11 · FastAPI · Uvicorn · SQLite (stdlib)

### `api/main.py` — estructura interna

```python
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))   # dónde están los JSONLs
DB_PATH  = Path(os.getenv("DB_PATH",  "/db/labels.db"))  # base SQLite
```

#### Base de datos SQLite

Se crea automáticamente en el arranque (`@app.on_event("startup")`):

```sql
CREATE TABLE IF NOT EXISTS labels (
    key     TEXT PRIMARY KEY,           -- NUM_INTERCONSULTA o ID del registro
    status  TEXT NOT NULL               -- 'valid' | 'invalid'
             CHECK(status IN ('valid','invalid')),
    note    TEXT NOT NULL DEFAULT ''    -- justificación del auditor
)
```

`INSERT OR REPLACE` permite upsert atómico: si la clave ya existe, la
actualiza; si no, la inserta.

#### Seguridad path traversal

Antes de leer un archivo JSONL se resuelve la ruta y se verifica que esté
dentro de `DATA_DIR`:

```python
path = (DATA_DIR / filename).resolve()
if DATA_DIR.resolve() not in path.parents:
    raise HTTPException(400, "Nombre de archivo inválido")
```

Esto evita peticiones como `GET /api/records/../../etc/passwd`.

#### Lectura de JSONL

Se parsea línea a línea para soportar archivos grandes sin cargar todo en
memoria de una vez:

```python
for line in f:
    line = line.strip()
    if line:
        records.append(json.loads(line))
```

### `api/Dockerfile`

```dockerfile
FROM python:3.11-slim          # imagen base mínima (~60 MB)
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### `api/requirements.txt`

```
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
pydantic>=2.0.0
```

---

## 5. Servicio Frontend (`frontend/`)

**Tecnologías:** Python 3.11 · Streamlit · requests

### `frontend/app.py` — estructura interna

#### Capa de comunicación con la API

```python
API_URL = os.getenv("API_URL", "http://localhost:8000")

@st.cache_data(ttl=120)          # cache 2 min: lista de archivos
def fetch_files() -> list[str]: ...

@st.cache_data(ttl=300)          # cache 5 min: registros de un JSONL
def fetch_records(filename) -> list[dict]: ...

def _api_get_labels() -> dict:   # sin cache (estado mutable)
def _api_set_label(...): ...     # PUT
def _api_delete_label(...): ...  # DELETE
```

El cache de `fetch_records` es crítico: con 1 192 registros por archivo,
sin caché cada interacción del usuario provocaría un re-fetch completo.
Con TTL 5 min, Streamlit reutiliza la lista en memoria entre reruns.

#### Ciclo de render de Streamlit

Streamlit re-ejecuta `main()` completo con cada interacción del usuario.
El flujo en cada ejecución es:

```
main()
 ├─ fetch_files()             → resultado cacheado
 ├─ ensure_session_defaults() → carga labels de API solo 1a vez (flag "labels_loaded")
 ├─ sidebar: filtros + bandeja
 ├─ fetch_records(choice)     → resultado cacheado
 ├─ filter_records(...)       → filtrado en memoria (Python puro)
 ├─ topbar HTML
 ├─ columna izquierda: tarjetas de lista
 └─ columna derecha: detalle del registro activo
        └─ Panel de resolución médica
               ├─ [Validar pertinencia]  → PUT /api/labels + st.rerun()
               ├─ [Rechazar solicitud]   → PUT /api/labels + st.rerun()
               └─ [Volver a pendiente]   → DELETE /api/labels + st.rerun()
```

#### Layout visual (tres zonas)

```
┌─────────────────────────────────────────────────────┐
│ Sidebar oscuro (#0f172a)                             │
│  · Logo DocRef Dashboard                             │
│  · Selectbox: archivo .jsonl                         │
│  · Radio: Pendientes / Validadas / Invalidadas / Todos│
│  · Badges con contadores                             │
│  · Filtros: especialidad, prioridad, búsqueda libre  │
└─────────────────────────────────────────────────────┘

Área principal:
┌──────────────────────────────────────────────────────┐
│ Topbar: [IC #FOLIO]  Expediente de Interconsulta  [ESTADO] │
├──────────────────┬───────────────────────────────────┤
│ Lista (38%)      │ Detalle (62%)                      │
│                  │                                    │
│ Tarjeta folio 1  │ Fila 1:                            │
│ Tarjeta folio 2  │   [Info paciente][Origen][Destino] │
│ ...              │                                    │
│                  │ Fila 2:                            │
│                  │   [Historia clínica][Panel validación]│
└──────────────────┴───────────────────────────────────┘
```

#### Funciones auxiliares clave

| Función | Qué hace |
|---|---|
| `record_key(row, fallback)` | Extrae la clave única: prioriza `NUM_INTERCONSULTA`, cae a `ID`, luego al índice |
| `label_status(key, labels)` | Traduce `"valid"/"invalid"/None` → `"validada"/"invalidada"/"pendiente"` |
| `audit_badge(status)` | Texto del pill superior: `"AUDITADA"/"RECHAZADA"/"PENDIENTE AUDICIÓN"` |
| `ges_active(row)` | Detecta si el registro es GES/AUGE revisando `ESTADO_AUGE` y `PROBLEMA_SALUD` |
| `filter_records(...)` | Filtro combinado: búsqueda libre + estado + especialidad + prioridad |
| `count_by_status(...)` | Contadores para los badges del sidebar |
| `priority_label(raw)` | Convierte `"1"/"2"/"3"` → texto + color del badge |

### `frontend/.streamlit/config.toml`

```toml
[theme]
base = "light"
primaryColor = "#2563eb"       # azul para botones primarios
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f4f6f9"
textColor = "#111827"

[server]
headless = true                # sin abrir navegador al arrancar
enableCORS = false
```

### `frontend/Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "app.py",
     "--server.port=8501",
     "--server.address=0.0.0.0",
     "--server.headless=true"]
```

---

## 6. Datos (`data/`)

La carpeta `data/` es la única fuente de datos de interconsultas. No hay
importación ni carga inicial a una base de datos: la API lee los archivos
directamente en cada request (con cache en el frontend).

### Formato JSONL

Cada línea es un objeto JSON independiente. Ejemplo de un registro:

```json
{
  "NUM_INTERCONSULTA": 212616149,
  "FECHA_IC": "2022-12-22 15:55:00",
  "ESTABLECIMIENTO_ORIGEN": "CESFAM VILLARRICA",
  "ESPECIALIDAD_ORIGEN": "MEDICINA GENERAL",
  "ESTABLECIMIENTO_DESTINO": "CESFAM VILLARRICA",
  "ESPECIALIDAD_DESTINO": "OFTALMOLOGIA",
  "TIPO_DERIVACION": "ENTRE ESPECIALIDADES INTRA HOSPITALARIAS",
  "MOTIVO_INTERCONSULTA": "CONSULTA",
  "COD_DIAGNO": "H524",
  "NOM_DIAGNOSTICO": "VICIO REFRACCION PRESBICIA",
  "ESTADO_AUGE": "NO GES",
  "PROBLEMA_SALUD": "NO TIENE",
  "EDAD_AÑOS": 54,
  "PREVISION_IC": "FONASA - B",
  "ID": "2616149",
  "ID_PACIENTE": "1364380",
  "HISTORIA_CLINICA": "...",
  "SE_REQUIERE": "EVALUACION MEDICO .",
  "EXAMENES_COMPLEMENTARIOS": null,
  "DERIVADO_PARA": "CONFIRMACION DIAGNOSTICA",
  "PRIORIDAD_DESTINO": "3"
}
```

### Campos que usa la UI

| Campo | Dónde se muestra |
|---|---|
| `NUM_INTERCONSULTA` | Folio en tarjeta y topbar · clave única de validación |
| `ID` | Fallback de clave si no hay `NUM_INTERCONSULTA` |
| `NOM_DIAGNOSTICO` | Título de la tarjeta y del detalle |
| `COD_DIAGNO` | Badge CIE-10 en historia clínica |
| `ESTABLECIMIENTO_ORIGEN/DESTINO` | Tarjeta y panel de origen/destino |
| `ESPECIALIDAD_ORIGEN/DESTINO` | Filtro sidebar + panel origen/destino |
| `FECHA_IC` | Fecha en tarjeta y detalle |
| `HISTORIA_CLINICA` | Textarea de solo lectura en detalle |
| `EXAMENES_COMPLEMENTARIOS` | Textarea o aviso amarillo si es null |
| `SE_REQUIERE` | Panel de requerimientos clínicos |
| `ESTADO_AUGE` | Detección GES (badge azul) |
| `PROBLEMA_SALUD` | Detección GES secundaria + kv de paciente |
| `PRIORIDAD_DESTINO` | Filtro sidebar + badge (1=alta/2=media/3=baja) |
| `ID_PACIENTE` | kv información del paciente |
| `EDAD_AÑOS` + `TIPO_EDAD` | kv información del paciente |
| `PREVISION_IC` | kv información del paciente |
| `DERIVADO_PARA` | Panel destino + requerimientos |
| `MOTIVO_INTERCONSULTA` | Panel requerimientos |
| `POLICLINICO_DESTINO` | Panel destino |
| `TIPO_DERIVACION` | Panel origen |

### Agregar un nuevo archivo de datos

Copiar cualquier `.jsonl` a la carpeta `data/`. No requiere reiniciar
Docker; aparece en el selectbox en la próxima recarga del frontend
(el cache de `fetch_files` expira en 2 minutos o al recargar la página).

---

## 7. Docker y despliegue

### `docker-compose.yml` explicado

```yaml
services:

  api:
    build: ./api                    # construye desde api/Dockerfile
    ports: ["8000:8000"]
    volumes:
      - ./data:/data:ro             # carpeta data/ mapeada como solo lectura
      - labels_db:/db               # volumen nombrado para SQLite
    environment:
      DATA_DIR: /data               # ruta interna de los JSONLs
      DB_PATH:  /db/labels.db       # ruta interna de la base SQLite
    healthcheck:
      test: [python -c "urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 15s
      retries: 5
      start_period: 10s             # tiempo para arrancar uvicorn

  frontend:
    build: ./frontend               # construye desde frontend/Dockerfile
    ports: ["8501:8501"]
    environment:
      API_URL: http://api:8000      # nombre de servicio Docker como hostname
    depends_on:
      api:
        condition: service_healthy  # espera hasta que api responda OK

volumes:
  labels_db:                        # volumen gestionado por Docker
    driver: local
```

**Por qué `http://api:8000` y no `http://localhost:8000`:**
Dentro de la red de Docker Compose cada servicio se resuelve por su nombre
(`api`, `frontend`). `localhost` apuntaría al propio contenedor del frontend,
no al contenedor de la API.

### Comandos útiles

```bash
# Levantar todo (construyendo imágenes si cambia el código)
docker compose up --build

# Solo en segundo plano
docker compose up -d --build

# Ver logs en tiempo real
docker compose logs -f

# Ver logs solo de un servicio
docker compose logs -f api
docker compose logs -f frontend

# Detener (conserva el volumen labels_db)
docker compose down

# Detener Y borrar todas las validaciones guardadas
docker compose down -v

# Reconstruir solo un servicio sin tocar el otro
docker compose up --build api
```

---

## 8. Variables de entorno

| Variable | Servicio | Default local | Valor en Docker |
|---|---|---|---|
| `DATA_DIR` | api | `/data` | `/data` |
| `DB_PATH` | api | `/db/labels.db` | `/db/labels.db` |
| `API_URL` | frontend | `http://localhost:8000` | `http://api:8000` |

---

## 9. Endpoints de la API

Documentación interactiva disponible en http://localhost:8000/docs (Swagger UI).

### `GET /health`
Health check. Responde `{"status": "ok"}`. Lo usa Docker para verificar
que la API esté lista antes de arrancar el frontend.

### `GET /api/files`
Lista los archivos `.jsonl` disponibles en `DATA_DIR`.

**Respuesta:**
```json
["OFTALMOLOGIA.jsonl", "MEDICINA_INTERNA.jsonl"]
```

### `GET /api/records/{filename}`
Devuelve todos los registros de un archivo JSONL como lista de objetos JSON.
Valida que el nombre no contenga path traversal.

**Respuesta:** `[ { ...registro... }, ... ]`

### `GET /api/labels`
Devuelve todas las validaciones guardadas en SQLite.

**Respuesta:**
```json
{
  "212616165": { "status": "valid",   "note": "Pertinencia confirmada" },
  "212616166": { "status": "invalid", "note": "Diagnóstico incompleto" }
}
```

### `PUT /api/labels/{key}`
Crea o actualiza una validación (upsert).

**Body:**
```json
{ "status": "valid", "note": "Texto de justificación" }
```
`status` acepta solo `"valid"` o `"invalid"`. Devuelve `{"ok": true}`.

### `DELETE /api/labels/{key}`
Borra una validación (vuelve el registro a estado "pendiente").

### `GET /api/export`
Exporta todas las validaciones como lista ordenada. Útil para descargar
el resultado de la auditoría.

**Respuesta:** `[ {"key":"...", "status":"...", "note":"..."}, ... ]`

---

## 10. Persistencia y volúmenes

```
Docker host                    Contenedor api
─────────────────────────────────────────────
./data/          ──(ro)──▶  /data/            ← JSONLs (lectura)
volumen labels_db ─────▶  /db/labels.db       ← SQLite (escritura)
```

- **`./data/`** se monta en modo solo lectura (`:ro`). La API no puede
  modificar los archivos originales.
- **`labels_db`** es un volumen Docker nombrado, gestionado por el daemon.
  Sobrevive a `docker compose down` pero se borra con `docker compose down -v`.
- Si el volumen aún no existe al arrancar, `_init_db()` crea la tabla
  automáticamente al primer inicio de la API.

---

## 11. Desarrollo local sin Docker

### Solo la API

```bash
cd api
pip install -r requirements.txt
$env:DATA_DIR = "..\data"        # PowerShell
$env:DB_PATH  = ".\labels.db"
uvicorn main:app --reload --port 8000
```

### Solo el Frontend (apuntando a la API local)

```bash
cd frontend
pip install -r requirements.txt
$env:API_URL = "http://localhost:8000"   # PowerShell
streamlit run app.py
```

### Standalone (sin API, sin Docker)

El archivo `app.py` en la raíz del proyecto lee los JSONL directamente
sin necesitar la API. Los labels se guardan solo en `session_state`
(se pierden al cerrar el navegador).

```bash
pip install streamlit
streamlit run app.py
```

---

## 12. Agregar nuevos datos

### Agregar un nuevo archivo JSONL

1. Copiar el archivo `.jsonl` a la carpeta `data/`.
2. En el frontend, recargar la página (F5). El selectbox mostrará el nuevo
   archivo (el cache de `fetch_files` dura 2 minutos).
3. No es necesario reiniciar Docker.

### Requisitos mínimos del JSONL

Cada línea debe ser un JSON válido con al menos uno de estos campos
para que el sistema pueda identificar el registro:

- `NUM_INTERCONSULTA` (preferido) — número entero o string
- `ID` — fallback si no existe `NUM_INTERCONSULTA`

El resto de campos son opcionales; si faltan se muestran como `—` en la UI.
