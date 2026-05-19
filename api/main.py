"""
API REST para el panel de interconsultas.
- PostgreSQL como almacenamiento principal
- Siembra automática desde archivos JSON en /data al primer arranque
- Persiste labels/notas de auditoría en la misma DB
- Campo `validado` (BOOLEAN) en `interconsultas`:
    TRUE  → pertinencia validada
    FALSE → solicitud rechazada
    NULL  → pendiente de auditoría
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

import psycopg2
import psycopg2.extras
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Interconsultas API", version="2.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR     = Path(os.getenv("DATA_DIR", "/data"))
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://interconsultas:interconsultas@db:5432/interconsultas",
)


# ── Conexión ──────────────────────────────────────────────────────────────────

def _conn() -> psycopg2.extensions.connection:
    return psycopg2.connect(DATABASE_URL)


# ── Inicialización y semilla ──────────────────────────────────────────────────

def _init_schema(cur: psycopg2.extensions.cursor) -> None:
    # Tabla principal: cada fila es un registro de interconsulta
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS interconsultas (
            id                BIGSERIAL PRIMARY KEY,
            fuente            TEXT      NOT NULL,
            num_interconsulta TEXT,
            validado          BOOLEAN   DEFAULT NULL,   -- TRUE=válida / FALSE=rechazada / NULL=pendiente
            nota_auditoria    TEXT      NOT NULL DEFAULT '',
            record            JSONB     NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_ic_fuente ON interconsultas (fuente);
        CREATE INDEX IF NOT EXISTS idx_ic_num    ON interconsultas (num_interconsulta);
        """
    )
    # Tabla de labels (compatibilidad con versiones anteriores + notas)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS labels (
            key     TEXT PRIMARY KEY,
            status  TEXT NOT NULL CHECK (status IN ('valid', 'invalid')),
            note    TEXT NOT NULL DEFAULT ''
        );
        """
    )
    # Tabla de reclamos: un auditor "reclama" un registro para indicar que lo está revisando
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS claims (
            key        TEXT PRIMARY KEY,
            auditor    TEXT NOT NULL,
            claimed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    # Migración no destructiva: agregar columnas si no existen (por si la DB
    # fue creada con una versión anterior de este esquema)
    for col, definition in [
        ("num_interconsulta", "TEXT"),
        ("validado",          "BOOLEAN DEFAULT NULL"),
        ("nota_auditoria",    "TEXT NOT NULL DEFAULT ''"),
    ]:
        cur.execute(
            """
            ALTER TABLE interconsultas
            ADD COLUMN IF NOT EXISTS %s %s
            """ % (col, definition)
        )


def _seed(cur: psycopg2.extensions.cursor) -> None:
    """
    Carga cada archivo *.json de DATA_DIR como un conjunto de registros.
    Solo se ejecuta si la tabla `interconsultas` está vacía.
    """
    cur.execute("SELECT COUNT(*) FROM interconsultas")
    if cur.fetchone()[0] > 0:
        return  # ya sembrado

    json_files = sorted(DATA_DIR.glob("*.json"))
    if not json_files:
        print(f"[seed] No se encontraron archivos JSON en {DATA_DIR}")
        return

    for path in json_files:
        fuente = path.stem
        try:
            records: list[dict] = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[seed] Error leyendo {path.name}: {exc}")
            continue

        if not isinstance(records, list):
            print(f"[seed] {path.name} no contiene un array JSON, se omite.")
            continue

        rows = [
            (
                fuente,
                str(r.get("NUM_INTERCONSULTA", "")) or None,
                json.dumps(r, ensure_ascii=False),
            )
            for r in records
        ]
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO interconsultas (fuente, num_interconsulta, record)
            VALUES %s
            """,
            rows,
            template="(%s, %s, %s::jsonb)",
            page_size=500,
        )
        print(f"[seed] {len(records):,} registros insertados desde {path.name}")


def _startup_with_retry(max_attempts: int = 20, delay: float = 3.0) -> None:
    for attempt in range(1, max_attempts + 1):
        try:
            with _conn() as conn:
                with conn.cursor() as cur:
                    _init_schema(cur)
                    _seed(cur)
                conn.commit()
            print("[startup] Base de datos lista.")
            return
        except psycopg2.OperationalError as exc:
            print(f"[startup] DB no disponible (intento {attempt}/{max_attempts}): {exc}")
            if attempt == max_attempts:
                raise
            time.sleep(delay)


@app.on_event("startup")
def on_startup() -> None:
    _startup_with_retry()


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# ── Fuentes disponibles ───────────────────────────────────────────────────────

@app.get("/api/files")
def list_files() -> list[str]:
    """Devuelve los nombres distintos de fuente."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT fuente FROM interconsultas ORDER BY fuente")
            return [row[0] for row in cur.fetchall()]


# ── Registros ─────────────────────────────────────────────────────────────────

@app.get("/api/records/{fuente}")
def get_records(fuente: str, page: int = 1, page_size: int = 50) -> dict:
    """
    Devuelve registros paginados de una fuente.
    Respuesta: { total, page, page_size, records: [...] }
    Cada registro incluye `_validado` (True/False/None) y `_nota_auditoria`.
    """
    page = max(1, page)
    page_size = max(1, min(page_size, 200))
    offset = (page - 1) * page_size

    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM interconsultas WHERE fuente = %s",
                (fuente,),
            )
            total: int = cur.fetchone()[0]

            cur.execute(
                """
                SELECT record, validado, nota_auditoria
                FROM   interconsultas
                WHERE  fuente = %s
                ORDER  BY id
                LIMIT  %s OFFSET %s
                """,
                (fuente, page_size, offset),
            )
            rows = cur.fetchall()

    if total == 0:
        raise HTTPException(status_code=404, detail=f"Fuente '{fuente}' no encontrada")

    records = []
    for record, validado, nota in rows:
        record["_validado"]       = validado
        record["_nota_auditoria"] = nota or ""
        records.append(record)

    return {"total": total, "page": page, "page_size": page_size, "records": records}


# ── Labels (validación de interconsultas) ─────────────────────────────────────

@app.get("/api/labels")
def get_all_labels() -> dict:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT key, status, note FROM labels")
            rows = cur.fetchall()
    return {r[0]: {"status": r[1], "note": r[2]} for r in rows}


class LabelIn(BaseModel):
    status: str
    note: Optional[str] = ""


@app.put("/api/labels/{key}")
def upsert_label(key: str, body: LabelIn) -> dict:
    """
    Guarda la decisión de auditoría.
    Actualiza:
      - tabla `labels`  (compatibilidad)
      - columna `validado` en `interconsultas` (TRUE/FALSE)
      - columna `nota_auditoria` en `interconsultas`
    """
    if body.status not in ("valid", "invalid"):
        raise HTTPException(status_code=400, detail="status debe ser 'valid' o 'invalid'")

    validado = body.status == "valid"   # True o False
    note = body.note or ""

    with _conn() as conn:
        with conn.cursor() as cur:
            # Tabla labels (compatibilidad)
            cur.execute(
                """
                INSERT INTO labels (key, status, note) VALUES (%s, %s, %s)
                ON CONFLICT (key) DO UPDATE
                    SET status = EXCLUDED.status,
                        note   = EXCLUDED.note
                """,
                (key, body.status, note),
            )
            # Campo validado en interconsultas
            cur.execute(
                """
                UPDATE interconsultas
                SET    validado       = %s,
                       nota_auditoria = %s
                WHERE  num_interconsulta = %s
                """,
                (validado, note, key),
            )
        conn.commit()
    return {"ok": True, "validado": validado}


@app.delete("/api/labels/{key}")
def delete_label(key: str) -> dict:
    """
    Revierte una interconsulta a estado pendiente.
    Elimina de `labels` y pone `validado = NULL` en `interconsultas`.
    """
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM labels WHERE key = %s", (key,))
            cur.execute(
                """
                UPDATE interconsultas
                SET    validado       = NULL,
                       nota_auditoria = ''
                WHERE  num_interconsulta = %s
                """,
                (key,),
            )
        conn.commit()
    return {"ok": True, "validado": None}


# ── Exportar validaciones ─────────────────────────────────────────────────────

@app.get("/api/export")
def export_all() -> list[dict]:
    """Exporta todas las interconsultas auditadas (validado IS NOT NULL)."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT record, validado, nota_auditoria, num_interconsulta, fuente
                FROM   interconsultas
                WHERE  validado IS NOT NULL
                ORDER  BY fuente, num_interconsulta
                """
            )
            rows = cur.fetchall()
    return [
        {**rec, "validado": v, "nota_auditoria": nota or "",
         "_fuente": fuente, "_num_interconsulta": num_ic}
        for rec, v, nota, num_ic, fuente in rows
    ]


@app.get("/api/export/{fuente}")
def export_by_fuente(fuente: str) -> list[dict]:
    """
    Exporta los registros auditados de una fuente específica.
    Cada registro incluye todos los campos originales más:
      - validado       : true (pertinente) | false (rechazada)
      - nota_auditoria : observación del médico auditor
    """
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT record, validado, nota_auditoria
                FROM   interconsultas
                WHERE  fuente = %s AND validado IS NOT NULL
                ORDER  BY id
                """,
                (fuente,),
            )
            rows = cur.fetchall()
    if not rows:
        return []
    result = []
    for rec, v, nota in rows:
        rec["validado"]       = v
        rec["nota_auditoria"] = nota or ""
        result.append(rec)
    return result


@app.get("/api/export-stats")
def export_stats() -> list[dict]:
    """Contadores de validadas / rechazadas / pendientes por fuente."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    fuente,
                    SUM(CASE WHEN validado IS TRUE  THEN 1 ELSE 0 END) AS validadas,
                    SUM(CASE WHEN validado IS FALSE THEN 1 ELSE 0 END) AS rechazadas,
                    SUM(CASE WHEN validado IS NULL  THEN 1 ELSE 0 END) AS pendientes,
                    COUNT(*) AS total
                FROM  interconsultas
                GROUP BY fuente
                ORDER BY fuente
                """
            )
            rows = cur.fetchall()
    return [
        {
            "fuente":     r[0],
            "validadas":  int(r[1] or 0),
            "rechazadas": int(r[2] or 0),
            "pendientes": int(r[3] or 0),
            "total":      int(r[4] or 0),
        }
        for r in rows
    ]


# ── Estadísticas rápidas ──────────────────────────────────────────────────────

@app.get("/api/stats")
def stats() -> dict:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT fuente, COUNT(*) FROM interconsultas GROUP BY fuente ORDER BY fuente"
            )
            totals = {r[0]: r[1] for r in cur.fetchall()}
            cur.execute(
                """
                SELECT
                    SUM(CASE WHEN validado IS TRUE  THEN 1 ELSE 0 END) AS validadas,
                    SUM(CASE WHEN validado IS FALSE THEN 1 ELSE 0 END) AS rechazadas,
                    SUM(CASE WHEN validado IS NULL  THEN 1 ELSE 0 END) AS pendientes
                FROM interconsultas
                """
            )
            row = cur.fetchone()
    return {
        "totales_por_fuente": totals,
        "validadas":  int(row[0] or 0),
        "rechazadas": int(row[1] or 0),
        "pendientes": int(row[2] or 0),
    }


# ── Claims (bloqueo de registro en revisión) ──────────────────────────────────

CLAIM_TTL_MINUTES     = 2   # tiempo máximo sin heartbeat antes de expirar
STALE_CLAIM_SECONDS   = 45  # si no hubo heartbeat en este tiempo, el claim es "obsoleto"
                             # y otra sesión puede tomarlo automáticamente


@app.get("/api/claims")
def get_claims() -> dict:
    """
    Devuelve todos los reclamos activos (no expirados).
    Formato: { key: auditor, ... }
    """
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT key, auditor FROM claims
                WHERE claimed_at > NOW() - INTERVAL '%s minutes'
                """,
                (CLAIM_TTL_MINUTES,),
            )
            rows = cur.fetchall()
    return {r[0]: r[1] for r in rows}


@app.post("/api/claims/{key}", status_code=200)
def claim_record(key: str, auditor: str) -> dict:
    """
    Reclama un registro para el auditor indicado.
    - Mismo auditor (renovación/heartbeat) → 200.
    - Otro auditor con claim FRESCO (< STALE_CLAIM_SECONDS) → 409 bloqueado.
    - Otro auditor con claim OBSOLETO (>= STALE_CLAIM_SECONDS, sin heartbeat) → override 200.
    - Sin claim activo → 200.
    """
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT auditor,
                       EXTRACT(EPOCH FROM (NOW() - claimed_at))::int AS age_seconds
                FROM   claims
                WHERE  key = %s
                  AND  claimed_at > NOW() - INTERVAL '%s minutes'
                """,
                (key, CLAIM_TTL_MINUTES),
            )
            row = cur.fetchone()

        if row:
            existing_auditor, age_seconds = row
            if existing_auditor != auditor and age_seconds < STALE_CLAIM_SECONDS:
                raise HTTPException(
                    status_code=409,
                    detail=f"En revisión por {existing_auditor}",
                )
            # Si es obsoleto (sin heartbeat) o es el mismo auditor → override permitido

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO claims (key, auditor, claimed_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (key) DO UPDATE
                    SET auditor    = EXCLUDED.auditor,
                        claimed_at = EXCLUDED.claimed_at
                """,
                (key, auditor),
            )
        conn.commit()
    return {"ok": True, "key": key, "auditor": auditor}


@app.delete("/api/claims/{key}")
def release_claim(key: str) -> dict:
    """Libera el reclamo de un registro."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM claims WHERE key = %s", (key,))
        conn.commit()
    return {"ok": True}


@app.post("/api/claims/{key}/release", status_code=200)
def release_claim_post(key: str) -> dict:
    """
    Igual que DELETE /api/claims/{key} pero en POST.
    Permite usar navigator.sendBeacon() desde el navegador al cerrar la pestaña.
    """
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM claims WHERE key = %s", (key,))
        conn.commit()
    return {"ok": True}


@app.post("/api/claims/{key}/heartbeat")
def heartbeat_claim(key: str, auditor: str) -> dict:
    """
    Renueva el timestamp de un reclamo existente para evitar que expire
    mientras el auditor sigue trabajando en el registro.
    """
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE claims SET claimed_at = NOW()
                WHERE key = %s AND auditor = %s
                """,
                (key, auditor),
            )
        conn.commit()
    return {"ok": True}
