"""
Panel tipo dashboard para revisar interconsultas (JSONL) y validar registros.
Sin autenticación: abierto para cualquier médico auditor.
"""

from __future__ import annotations

import json
import os
import random
import string
from datetime import datetime
from pathlib import Path

import requests
import streamlit as st

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"

API_URL = os.getenv("API_URL", "http://localhost:8000")

MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}


# ── Estilos ───────────────────────────────────────────────────────────────────

def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        /* ── Reset base ── */
        .stApp { background-color: #f8fafc !important; color: #111827 !important; }
        [data-testid="stAppViewContainer"],
        [data-testid="stHeader"],
        [data-testid="stToolbar"] { background-color: #f8fafc !important; }
        html, body { background-color: #f8fafc !important; }

        /* ── Sidebar: fondo oscuro ── */
        section[data-testid="stSidebar"],
        div[data-testid="stSidebar"] {
            background: #0f172a !important;
            border-right: 1px solid #1e293b !important;
        }

        /* Ocultar la navegación automática de Streamlit (páginas) */
        [data-testid="stSidebarNav"],
        [data-testid="stSidebarNavItems"],
        [data-testid="stSidebarNavSeparator"] { display: none !important; }

        /* Todo el texto del sidebar en claro */
        [data-testid="stSidebar"],
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] div,
        [data-testid="stSidebar"] small,
        [data-testid="stSidebar"] a {
            color: #e2e8f0 !important;
            -webkit-text-fill-color: #e2e8f0 !important;
        }
        [data-testid="stSidebar"] [data-testid="stCaption"],
        [data-testid="stSidebar"] [data-testid="stCaption"] p {
            color: #94a3b8 !important;
            -webkit-text-fill-color: #94a3b8 !important;
        }

        /* Inputs y selectbox: fondo visible */
        [data-testid="stSidebar"] [data-baseweb="base-input"],
        [data-testid="stSidebar"] [data-baseweb="select"] > div:first-child {
            background-color: #1e293b !important;
            border-color: #334155 !important;
        }
        [data-testid="stSidebar"] [data-baseweb="select"] *,
        [data-testid="stSidebar"] [data-baseweb="input"] input,
        [data-testid="stSidebar"] input {
            color: #e2e8f0 !important;
            -webkit-text-fill-color: #e2e8f0 !important;
            background-color: transparent !important;
        }
        [data-testid="stSidebar"] input::placeholder {
            color: #475569 !important;
            -webkit-text-fill-color: #475569 !important;
        }

        /* Radio buttons */
        [data-testid="stSidebar"] [data-testid="stRadio"] label p,
        [data-testid="stSidebar"] [role="radiogroup"] label p {
            color: #e2e8f0 !important;
            -webkit-text-fill-color: #e2e8f0 !important;
        }
        [data-testid="stSidebar"] [data-baseweb="radio"] > div:first-child {
            border-color: #475569 !important;
            background-color: transparent !important;
        }
        [data-testid="stSidebar"] [aria-checked="true"] > div:first-child {
            border-color: #3b82f6 !important;
            background-color: #3b82f6 !important;
        }

        /* Divider */
        [data-testid="stSidebar"] hr { border-color: #1e293b !important; }

        /* ── Content ── */
        .main .block-container {
            padding-top: 1rem; padding-bottom: 2rem;
            max-width: 1600px; background-color: #f8fafc !important;
        }
        div[data-testid="stMarkdownContainer"] p,
        div[data-testid="stMarkdownContainer"] li { color: #111827 !important; }
        [data-baseweb="select"] > div,
        [data-baseweb="input"] input {
            background-color: #fff !important; color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
        }
        .stTextArea textarea,
        [data-testid="stTextArea"] textarea {
            background-color: #fff !important; color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
            caret-color: #111827 !important; border-color: #e2e8f0 !important;
            font-size: .88rem !important; line-height: 1.55 !important;
        }
        .stTextArea textarea:disabled {
            background-color: #f8fafc !important; color: #374151 !important;
            -webkit-text-fill-color: #374151 !important; opacity: 1 !important;
        }
        [data-testid="stCaption"] { color: #6b7280 !important; }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background-color: #fff !important; border-color: #e5e7eb !important;
        }

        /* ── Botones ── */
        .stButton > button[kind="primary"] {
            background-color: #2563eb !important; color: #fff !important;
            border: none !important; font-weight: 700 !important;
            border-radius: 8px !important; font-size: .85rem !important;
        }
        .stButton > button[kind="secondary"] {
            background-color: #fff !important; color: #374151 !important;
            border: 1px solid #d1d5db !important; font-weight: 600 !important;
            border-radius: 8px !important; font-size: .85rem !important;
        }
        .stButton > button:disabled { opacity: 0.5 !important; }

        /* ── Sidebar brand ── */
        .sb-brand { display:flex; align-items:center; gap:.55rem; margin-bottom:.3rem; }
        .sb-dot {
            width:9px; height:9px; border-radius:50%;
            background:#ef4444; box-shadow:0 0 0 3px rgba(239,68,68,.18);
            flex-shrink:0;
        }
        .sb-title { font-weight:800; font-size:1rem; letter-spacing:-.01em; color:#f1f5f9 !important; }
        .sb-sub   { color:#94a3b8 !important; font-size:.75rem; margin-top:.05rem; }
        .sb-item {
            display:flex; justify-content:space-between; align-items:center;
            padding:.5rem .6rem; border-radius:9px;
            border:1px solid rgba(148,163,184,.12);
            background:rgba(255,255,255,.03);
            font-weight:700; font-size:.88rem; color:#e2e8f0 !important;
        }
        .sb-item-active {
            border-color:rgba(239,68,68,.45) !important;
            background:rgba(239,68,68,.1) !important;
        }
        .sb-badge {
            background:#ef4444; color:#fff !important;
            border-radius:7px; padding:.03rem .42rem;
            font-size:.75rem; font-weight:800;
        }

        /* ── Top bar ── */
        .topbar {
            display:flex; align-items:center; justify-content:space-between;
            gap:1rem; padding:.3rem .1rem .7rem .1rem;
            border-bottom:2px solid #e5e7eb; margin-bottom:.8rem;
        }
        .topbar-left { display:flex; align-items:center; gap:.75rem; }
        .ic-pill {
            display:inline-flex; align-items:center;
            padding:.2rem .6rem; border-radius:6px;
            background:#dbeafe; color:#1e40af;
            font-weight:800; font-size:.78rem; border:1px solid #bfdbfe;
            letter-spacing:.03em;
        }
        .page-title { font-weight:800; font-size:1.12rem; color:#0f172a; }
        .status-pill {
            display:inline-flex; align-items:center;
            padding:.22rem .7rem; border-radius:6px;
            font-weight:800; font-size:.75rem; letter-spacing:.05em;
        }
        .status-pending  { background:#ffedd5; color:#9a3412; border:1px solid #fed7aa; }
        .status-valid    { background:#dcfce7; color:#166534; border:1px solid #bbf7d0; }
        .status-invalid  { background:#fee2e2; color:#b91c1c; border:1px solid #fecaca; }

        /* ── Info strip (3 columnas encabezado) ── */
        .info-box {
            background:#fff; border:1px solid #e5e7eb; border-radius:10px;
            padding:.65rem .9rem; height:100%;
        }
        .info-label {
            font-size:.68rem; font-weight:700; color:#9ca3af;
            text-transform:uppercase; letter-spacing:.06em; margin-bottom:.1rem;
        }
        .info-value { font-size:.9rem; font-weight:700; color:#111827; }
        .info-value-sm { font-size:.8rem; font-weight:600; color:#374151; }
        .info-value-link { font-size:.85rem; font-weight:700; color:#2563eb; }
        .info-section-sep {
            border-top:1px solid #f1f5f9; margin:.4rem 0;
        }
        .info-type-tag {
            font-size:.7rem; color:#6b7280; font-weight:500;
            text-transform:uppercase; letter-spacing:.04em;
        }
        .info-esp-tag {
            font-size:.78rem; font-weight:800; color:#b91c1c;
            text-transform:uppercase; letter-spacing:.01em;
        }

        /* ── Tarjetas del listado (izq) ── */
        .list-head { font-weight:700; color:#0f172a; font-size:.95rem; margin-bottom:.15rem; }
        .dash-muted { color:#64748b; font-size:.82rem; }
        .list-card {
            background:#fff; border:1px solid #e2e8f0; border-radius:10px;
            padding:.85rem 1rem; margin-bottom:.5rem;
            box-shadow:0 1px 2px rgba(15,23,42,.05);
        }
        .list-card-active {
            border:2px solid #2563eb !important;
            box-shadow:0 4px 14px rgba(37,99,235,.13) !important;
        }
        .list-folio { font-size:.72rem; font-weight:700; color:#94a3b8; letter-spacing:.06em; }
        .list-diag  { font-size:.92rem; font-weight:700; color:#0f172a; margin:.25rem 0 .2rem; }
        .list-meta  { font-size:.75rem; color:#64748b; line-height:1.4; }

        /* ── Badges ── */
        .badge {
            display:inline-block; padding:.12rem .5rem; border-radius:999px;
            font-size:.68rem; font-weight:700; margin-right:.3rem; vertical-align:middle;
        }
        .badge-green  { background:#dcfce7; color:#166534; }
        .badge-red    { background:#fee2e2; color:#b91c1c; }
        .badge-orange { background:#ffedd5; color:#c2410c; }
        .badge-blue   { background:#dbeafe; color:#1d4ed8; }
        .badge-gray   { background:#f1f5f9; color:#475569; }
        .badge-ges    { background:#ede9fe; color:#6d28d9; }

        /* ── Panel historia ── */
        .section-card {
            background:#fff; border:1px solid #e5e7eb; border-radius:12px;
            padding:1rem 1.1rem; margin-bottom:.6rem;
            box-shadow:0 1px 3px rgba(15,23,42,.04);
        }
        .section-header {
            display:flex; align-items:center; justify-content:space-between;
            margin-bottom:.55rem;
        }
        .section-title {
            font-size:.7rem; font-weight:800; color:#64748b;
            text-transform:uppercase; letter-spacing:.1em;
        }
        .cie-label {
            font-size:.7rem; font-weight:700; color:#94a3b8;
            text-transform:uppercase; letter-spacing:.06em;
        }
        .diag-name {
            font-size:1.25rem; font-weight:900; color:#0f172a;
            letter-spacing:-.02em; margin:.15rem 0 .6rem;
        }
        .relato-label {
            font-size:.68rem; font-weight:800; color:#94a3b8;
            text-transform:uppercase; letter-spacing:.08em; margin-bottom:.35rem;
        }

        /* ── Requerimientos ── */
        .req-row {
            display:flex; align-items:flex-start; gap:.75rem;
            padding:.5rem 0; border-bottom:1px solid #f1f5f9;
        }
        .req-row:last-child { border-bottom:none; }
        .req-key {
            font-size:.7rem; font-weight:700; color:#9ca3af;
            text-transform:uppercase; letter-spacing:.07em;
            min-width:80px; padding-top:.05rem;
        }
        .req-val { font-size:.88rem; font-weight:600; color:#111827; }

        /* ── Exámenes warning ── */
        .exam-warn {
            background:#fffbeb; border:1px solid #fde68a; border-radius:8px;
            padding:.55rem .8rem; font-size:.8rem; color:#92400e;
        }

        /* ── Resolución médica ── */
        .panel-label {
            font-size:.68rem; font-weight:800; color:#9ca3af;
            text-transform:uppercase; letter-spacing:.08em; margin-bottom:.3rem;
        }

        /* ── Footer bar ── */
        .footer-bar {
            display:flex; align-items:center; gap:1.5rem;
            padding:.6rem .9rem; margin-top:.5rem;
            background:#fff; border:1px solid #e5e7eb; border-radius:10px;
            font-size:.8rem;
        }
        .footer-item { display:flex; align-items:center; gap:.45rem; color:#374151; }
        .footer-label { font-size:.65rem; font-weight:700; color:#9ca3af; text-transform:uppercase; letter-spacing:.06em; display:block; }
        .footer-val   { font-weight:700; color:#111827; }
        .prio-dot {
            width:8px; height:8px; border-radius:50%; display:inline-block; margin-right:.3rem;
        }
        .prio-dot-orange { background:#f97316; }
        .prio-dot-red    { background:#ef4444; }
        .prio-dot-blue   { background:#3b82f6; }
        .prio-dot-gray   { background:#94a3b8; }

        /* ── Panel exportar ── */
        .export-panel {
            background:#fff; border:1px solid #e5e7eb; border-radius:12px;
            padding:1rem 1.2rem; margin-top:.6rem;
        }
        .export-title {
            font-size:.7rem; font-weight:800; color:#64748b;
            text-transform:uppercase; letter-spacing:.1em; margin-bottom:.75rem;
        }
        .export-row {
            display:flex; align-items:center; justify-content:space-between;
            padding:.55rem 0; border-bottom:1px solid #f1f5f9; gap:.5rem;
        }
        .export-row:last-child { border-bottom:none; padding-bottom:0; }
        .export-fuente {
            font-size:.82rem; font-weight:600; color:#374151;
            white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:55%;
        }
        .export-chips { display:flex; gap:.35rem; flex-shrink:0; }
        .chip-green { background:#dcfce7; color:#166534; border-radius:6px;
            padding:.1rem .45rem; font-size:.7rem; font-weight:700; }
        .chip-red   { background:#fee2e2; color:#b91c1c; border-radius:6px;
            padding:.1rem .45rem; font-size:.7rem; font-weight:700; }
        .chip-gray  { background:#f1f5f9; color:#6b7280; border-radius:6px;
            padding:.1rem .45rem; font-size:.7rem; font-weight:700; }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ── Capa de acceso a la API ────────────────────────────────────────────────────

def _api(method: str, path: str, **kwargs) -> requests.Response:
    """Wrapper de requests con timeout y manejo de errores básico."""
    url = f"{API_URL}{path}"
    r = getattr(requests, method)(url, timeout=15, **kwargs)
    r.raise_for_status()
    return r


@st.cache_data(show_spinner=False, ttl=30)
def api_get_files() -> list[str]:
    """Lista de fuentes disponibles en la API (nombre del stem del archivo)."""
    try:
        return _api("get", "/api/files").json()
    except Exception:
        return []


@st.cache_data(show_spinner=False, ttl=15)
def api_get_records(fuente: str) -> list[dict]:
    """
    Registros de una fuente con su estado de auditoría embebido:
      _validado: True / False / None
      _nota_auditoria: str
    """
    try:
        return _api("get", f"/api/records/{fuente}").json()
    except Exception:
        return []


@st.cache_data(show_spinner=False, ttl=15)
def api_get_all_records() -> list[dict]:
    """Todos los registros de todas las fuentes combinados (modo Todos)."""
    fuentes = api_get_files()
    combined: list[dict] = []
    for f in fuentes:
        rows = api_get_records(f)
        for r in rows:
            combined.append(dict(r, _src=fuente_display(f)))
    return combined


@st.cache_data(show_spinner=False, ttl=10)
def api_get_claims() -> dict[str, str]:
    """Reclamos activos: { key: auditor }."""
    try:
        return _api("get", "/api/claims").json()
    except Exception:
        return {}


def api_put_label(key: str, status: str, note: str) -> None:
    """Persiste la decisión de auditoría en PostgreSQL vía API."""
    _api("put", f"/api/labels/{key}", json={"status": status, "note": note})
    # Invalidar cachés afectadas
    api_get_records.clear()
    api_get_all_records.clear()


def api_claim(key: str, auditor: str) -> tuple[bool, str]:
    """
    Reclama el registro para el auditor.
    Devuelve (ok, mensaje_de_error).
    """
    try:
        _api("post", f"/api/claims/{key}", params={"auditor": auditor})
        api_get_claims.clear()
        return True, ""
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 409:
            detail = e.response.json().get("detail", "En revisión por otro auditor")
            return False, detail
        return False, str(e)
    except Exception as e:
        return False, str(e)


def api_release_claim(key: str) -> None:
    """Libera el reclamo del registro."""
    try:
        _api("delete", f"/api/claims/{key}")
        api_get_claims.clear()
    except Exception:
        pass


def api_heartbeat(key: str, auditor: str) -> None:
    """Renueva el reclamo para que no expire mientras el auditor sigue revisando."""
    try:
        _api("post", f"/api/claims/{key}/heartbeat", params={"auditor": auditor})
    except Exception:
        pass


# ── Utilidades de nombre de fuente ────────────────────────────────────────────

def fuente_display(fuente: str) -> str:
    """Convierte el stem del archivo en nombre legible para el selector."""
    name = fuente
    for prefix in ("interconsultas_mg_", "interconsultas_"):
        if name.lower().startswith(prefix):
            name = name[len(prefix):]
            break
    for suffix in ("_1000",):
        if name.lower().endswith(suffix):
            name = name[: -len(suffix)]
            break
    return name.replace("_", " ").title()


def load_records(choice: str) -> list[dict]:
    """Carga los registros según la selección del usuario."""
    if choice == "— Todos —":
        return api_get_all_records()
    fuentes = api_get_files()
    for f in fuentes:
        if fuente_display(f) == choice:
            return api_get_records(f)
    return []


# ── Utilidades ─────────────────────────────────────────────────────────────────

def fmt(val) -> str:
    if val is None:
        return "—"
    s = str(val).strip()
    return s if s else "—"


def short(s, n: int = 28) -> str:
    t = fmt(s)
    return t if (t == "—" or len(t) <= n) else t[:n] + "…"


def record_key(row: dict, fallback: str) -> str:
    src = row.get("_src", "")
    prefix = f"{src}|" if src else ""
    n = row.get("NUM_INTERCONSULTA")
    i = row.get("ID")
    if n is not None:
        return f"{prefix}{n}"
    if i is not None:
        return f"{prefix}{i}"
    return f"{prefix}{fallback}"


def label_status(key: str, labels: dict) -> str:
    """
    Determina el estado de un registro.
    Primero revisa el dict local de labels (compatibilidad y modo sin API),
    luego el campo _validado que viene de la API embebido en el registro.
    """
    v = labels.get(key)
    if v == "valid":
        return "validada"
    if v == "invalid":
        return "invalidada"
    return "pendiente"


def row_status(row: dict, key: str, labels: dict) -> str:
    """
    Estado real: usa _validado del registro (API) con fallback a labels local.
    """
    validado = row.get("_validado")  # True / False / None — viene de la API
    if validado is True:
        return "validada"
    if validado is False:
        return "invalidada"
    return label_status(key, labels)


def ges_active(row: dict) -> bool:
    auge = fmt(row.get("ESTADO_AUGE"))
    prob = fmt(row.get("PROBLEMA_SALUD"))
    return "GES" in auge.upper() or (prob not in ("—", "NO TIENE") and len(prob) > 3)


def priority_info(raw) -> tuple[str, str, str]:
    """Devuelve (texto, clase_dot, texto_nivel)."""
    if raw is None or str(raw).strip() == "":
        return "Sin prioridad", "prio-dot-gray", "Sin prioridad"
    s = str(raw).strip()
    if s == "1":
        return "Alta", "prio-dot-red", "Nivel 1 — Alta"
    if s == "2":
        return "Media", "prio-dot-orange", "Nivel 2"
    if s == "3":
        return "Baja", "prio-dot-blue", "Nivel 3 — Baja"
    return f"Nivel {s}", "prio-dot-gray", f"Nivel {s}"


def fmt_fecha_larga(fecha_str: str) -> str:
    try:
        dt = datetime.fromisoformat(str(fecha_str).replace(" ", "T").split("T")[0])
        return f"{dt.day} de {MESES_ES[dt.month]} de {dt.year}"
    except Exception:
        return fmt(fecha_str)


def count_by_status(records: list[dict], labels: dict) -> dict[str, int]:
    pend = val = inv = 0
    for idx, row in enumerate(records):
        key = record_key(row, str(idx))
        s = row_status(row, key, labels)
        if s == "pendiente":
            pend += 1
        elif s == "validada":
            val += 1
        else:
            inv += 1
    return {"Todos": len(records), "Pendientes": pend, "Validadas": val, "Invalidadas": inv}


def filter_records(
    records: list[dict],
    search: str,
    estado: str,
    espec: str,
    prio: str,
    labels: dict,
) -> list[tuple[str, dict]]:
    q = search.strip().lower()
    out: list[tuple[str, dict]] = []
    for idx, row in enumerate(records):
        key = record_key(row, str(idx))
        blob = " ".join(
            fmt(row.get(k)).lower()
            for k in ("NOM_DIAGNOSTICO", "HISTORIA_CLINICA",
                      "ESTABLECIMIENTO_ORIGEN", "ESTABLECIMIENTO_DESTINO",
                      "ID", "NUM_INTERCONSULTA")
        )
        if q and q not in blob:
            continue
        st_lbl = row_status(row, key, labels)
        if estado == "Pendientes" and st_lbl != "pendiente":
            continue
        if estado == "Validadas" and st_lbl != "validada":
            continue
        if estado == "Invalidadas" and st_lbl != "invalidada":
            continue
        esp = fmt(row.get("ESPECIALIDAD_DESTINO"))
        if espec != "Todos" and esp != espec:
            continue
        pr = fmt(row.get("PRIORIDAD_DESTINO"))
        if prio != "Todos" and pr != prio:
            continue
        out.append((key, row))
    return out


def _new_session_id() -> str:
    """Genera un ID de sesión corto y aleatorio, ej: Auditor-3F2A."""
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"Auditor-{suffix}"


def ensure_session_defaults() -> None:
    st.session_state.setdefault("label_by_key", {})
    st.session_state.setdefault("notes_by_key", {})
    st.session_state.setdefault("selected_key", None)
    st.session_state.setdefault("pending_confirm", None)
    st.session_state.setdefault("auditor_name", _new_session_id())  # asignado una vez por sesión
    st.session_state.setdefault("claimed_key", None)
    st.session_state.setdefault("claim_error", "")


# ── Modal de confirmación ──────────────────────────────────────────────────────

@st.dialog("Confirmar decisión de auditoría")
def modal_confirmacion(key: str, accion: str, nota: str) -> None:
    if accion == "valid":
        st.markdown(
            "### ¿Está seguro de **validar** esta interconsulta?",
        )
        st.info(
            "Una vez confirmada, la interconsulta quedará **validada** y "
            "no podrá volver a revisarse ni modificarse.",
        )
    else:
        st.markdown(
            "### ¿Está seguro de **rechazar** esta solicitud?",
        )
        st.warning(
            "Una vez confirmada, la interconsulta quedará **invalidada** y "
            "no podrá volver a revisarse ni modificarse.",
        )

    if nota.strip():
        st.markdown("**Observación registrada:**")
        st.caption(nota[:200] + ("…" if len(nota) > 200 else ""))

    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2 = st.columns(2, gap="small")
    with c1:
        btn_label = "✅ Sí, validar" if accion == "valid" else "❌ Sí, rechazar"
        if st.button(btn_label, type="primary", use_container_width=True, key="modal_confirm"):
            with st.spinner("Guardando decisión..."):
                try:
                    api_put_label(key, accion, nota)
                    # Liberar el reclamo tras decidir
                    auditor = st.session_state.get("auditor_name", "")
                    if auditor:
                        api_release_claim(key)
                    st.session_state.pending_confirm = None
                    st.rerun()
                except Exception as exc:
                    st.error(f"Error al guardar: {exc}")
    with c2:
        if st.button("Cancelar", use_container_width=True, key="modal_cancel"):
            st.session_state.pending_confirm = None
            st.rerun()


# ── Componentes UI ─────────────────────────────────────────────────────────────

def render_list_card(
    key: str, row: dict, selected: bool, labels: dict, claims: dict
) -> None:
    st_lbl = row_status(row, key, labels)
    ges = ges_active(row)
    diag = fmt(row.get("NOM_DIAGNOSTICO"))
    diag_short = diag[:46] + ("…" if len(diag) > 46 else "")
    folio = fmt(row.get("NUM_INTERCONSULTA"))
    origen = short(row.get("ESTABLECIMIENTO_ORIGEN"), 22)
    fecha = fmt(row.get("FECHA_IC")).split(" ")[0] if fmt(row.get("FECHA_IC")) != "—" else "—"

    auditor_self = st.session_state.get("auditor_name", "")
    claim_owner  = claims.get(key, "")

    if st_lbl == "validada":
        badge_html = '<span class="badge badge-green">Validada</span>'
    elif st_lbl == "invalidada":
        badge_html = '<span class="badge badge-red">Invalidada</span>'
    elif claim_owner and claim_owner != auditor_self:
        badge_html = f'<span class="badge badge-orange">En revisión</span>'
    else:
        badge_html = ""

    ges_html = '<span class="badge badge-ges">GES</span>' if ges else ""
    card_cls = "list-card list-card-active" if selected else "list-card"

    st.markdown(
        f"""
        <div class="{card_cls}">
          <div style="display:flex;justify-content:space-between;align-items:center;gap:.4rem;">
            <span class="list-folio">FOLIO {folio}</span>
            <span>{ges_html}{badge_html}</span>
          </div>
          <div class="list-diag">{diag_short}</div>
          <div class="list-meta">
            📍 {origen}<br>
            🗓 {fecha}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button(
        "▶ Abierta" if selected else "Abrir",
        key=f"pick_{key}",
        use_container_width=True,
        type="primary" if selected else "secondary",
    ):
        st.session_state.selected_key = key
        st.rerun()


def render_info_strip(row: dict) -> None:
    """Fila de 3 cajas: paciente | origen | destino."""
    col_a, col_b, col_c = st.columns([1.0, 1.1, 1.15], gap="small")

    edad = fmt(row.get("EDAD_AÑOS"))
    prevision = fmt(row.get("PREVISION_IC"))

    orig_estab = fmt(row.get("ESTABLECIMIENTO_ORIGEN"))
    orig_esp   = fmt(row.get("ESPECIALIDAD_ORIGEN"))
    tipo_deriv = fmt(row.get("TIPO_DERIVACION"))

    dest_estab = fmt(row.get("ESTABLECIMIENTO_DESTINO"))
    dest_poli  = fmt(row.get("POLICLINICO_DESTINO"))
    dest_esp   = fmt(row.get("GLOSA_ESP_DEIS_DEST")) or fmt(row.get("ESPECIALIDAD_DESTINO"))

    with col_a:
        st.markdown(
            f"""
            <div class="info-box">
              <div class="info-label">Paciente</div>
              <div class="info-value">Edad: {edad} años</div>
              <div class="info-section-sep"></div>
              <div class="info-label">Previsión</div>
              <div class="info-value-link">{prevision}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_b:
        st.markdown(
            f"""
            <div class="info-box">
              <div class="info-label">Especialidad Origen</div>
              <div class="info-value">{orig_estab}</div>
              <div class="info-value-sm" style="margin-top:.2rem;">{orig_esp}</div>
              <div class="info-section-sep"></div>
              <div class="info-type-tag">{tipo_deriv}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_c:
        st.markdown(
            f"""
            <div class="info-box">
              <div class="info-label">Especialidad / Policlínico</div>
              <div class="info-value">{dest_estab}</div>
              <div class="info-section-sep"></div>
              <div class="info-esp-tag">{dest_esp} / {dest_poli}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_historia(row: dict, key: str) -> None:
    ges = ges_active(row)
    ges_tag = "GES / AUGE" if ges else "NO GES / AUGE"
    ges_badge = (
        '<span class="badge badge-ges">GES / AUGE</span>'
        if ges else
        '<span class="badge badge-gray">NO GES / AUGE</span>'
    )
    diag_full = fmt(row.get("NOM_DIAGNOSTICO"))
    cod = fmt(row.get("COD_DIAGNO"))

    st.markdown(
        f"""
        <div class="section-card">
          <div class="section-header">
            <span class="section-title">Historia Clínica y Diagnóstico</span>
            {ges_badge}
          </div>
          <div class="cie-label">Diagnóstico CIE-10: <code style="font-size:.72rem;color:#374151;">{cod}</code></div>
          <div class="diag-name">{diag_full}</div>
          <div class="relato-label">Relato Clínico</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.text_area(
        "historia",
        value=fmt(row.get("HISTORIA_CLINICA")),
        height=220,
        disabled=True,
        label_visibility="collapsed",
        key=f"hist_{key}",
    )


def render_examenes(row: dict, key: str) -> None:
    exam = fmt(row.get("EXAMENES_COMPLEMENTARIOS"))
    st.markdown('<div class="panel-label">Exámenes Complementarios</div>', unsafe_allow_html=True)
    if exam == "—":
        st.markdown(
            '<div class="exam-warn">'
            '<em>No se registran exámenes adjuntos en este folio.</em>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.text_area(
            "examen",
            value=exam,
            height=90,
            disabled=True,
            label_visibility="collapsed",
            key=f"exam_{key}",
        )


def render_requerimientos(row: dict) -> None:
    motivo  = fmt(row.get("MOTIVO_INTERCONSULTA"))
    deriv   = fmt(row.get("DERIVADO_PARA"))
    req     = fmt(row.get("SE_REQUIERE"))

    st.markdown(
        f"""
        <div class="section-card" style="margin-bottom:.6rem;">
          <div class="section-title" style="margin-bottom:.5rem;">Requerimientos Clínicos</div>
          <div class="req-row">
            <span class="req-key">Motivo</span>
            <span class="req-val">{motivo}</span>
          </div>
          <div class="req-row">
            <span class="req-key">Derivación</span>
            <span class="req-val">{deriv}</span>
          </div>
          <div class="req-row">
            <span class="req-key">Requerido</span>
            <span class="req-val">{req}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_panel_resolucion(key: str, row: dict, labels: dict, claims: dict) -> None:
    st_lbl = row_status(row, key, labels)
    is_locked = st_lbl in ("validada", "invalidada")

    # Verificar si otro auditor tiene el registro reclamado
    auditor_self = st.session_state.get("auditor_name", "")
    claim_owner  = claims.get(key, "")
    blocked_by_other = claim_owner and claim_owner != auditor_self

    st.markdown(
        """
        <div class="section-card" style="margin-bottom:.4rem;">
          <div class="section-title" style="margin-bottom:.15rem;">Panel de Resolución Médica</div>
          <div class="panel-label">Justificación clínica de la auditoría</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if is_locked:
        saved_note = row.get("_nota_auditoria") or ""
        if st_lbl == "validada":
            st.success("✅ Interconsulta **validada**. Esta decisión es definitiva.")
        else:
            st.error("❌ Solicitud **rechazada**. Esta decisión es definitiva.")
        if saved_note.strip():
            st.text_area(
                "obs_locked",
                value=saved_note,
                height=90,
                disabled=True,
                label_visibility="collapsed",
                key=f"note_locked_{key}",
            )
        else:
            st.caption("Sin observaciones registradas.")
        return

    if blocked_by_other:
        st.warning(f"⏳ En revisión por **{claim_owner}**. Espera a que termine.")
        return

    note_key = f"note_input_{key}"
    if note_key not in st.session_state:
        saved = row.get("_nota_auditoria") or ""
        st.session_state[note_key] = saved

    new_note = st.text_area(
        "obs",
        key=note_key,
        height=120,
        placeholder="Ingrese las observaciones técnicas o motivos del rechazo/aprobación...",
        label_visibility="collapsed",
    )

    b1, b2 = st.columns(2, gap="small")
    with b1:
        if st.button(
            "Validar pertinencia",
            type="primary",
            use_container_width=True,
            key=f"v_ok_{key}",
        ):
            st.session_state.pending_confirm = {"key": key, "accion": "valid", "nota": new_note}
            st.rerun()
    with b2:
        if st.button(
            "Rechazar solicitud",
            type="secondary",
            use_container_width=True,
            key=f"v_bad_{key}",
        ):
            st.session_state.pending_confirm = {"key": key, "accion": "invalid", "nota": new_note}
            st.rerun()


def render_export_panel(
    all_records: list[dict],
    choice: str,
    labels: dict,
    files: list[Path] | None = None,
) -> None:
    """
    Panel de descarga con todas las interconsultas auditadas en la sesión.
    En modo 'Todos' muestra chips por fuente; en modo individual, un solo bloque.
    """
    validadas:  list[dict] = []
    rechazadas: list[dict] = []
    for idx, row in enumerate(all_records):
        key = record_key(row, str(idx))
        st_lbl = row_status(row, key, labels)
        export_row = {k: v for k, v in row.items() if k not in ("_src", "_validado", "_nota_auditoria")}
        if st_lbl == "validada":
            export_row["validado"]       = True
            export_row["nota_auditoria"] = st.session_state.notes_by_key.get(key, "")
            validadas.append(export_row)
        elif st_lbl == "invalidada":
            export_row["validado"]       = False
            export_row["nota_auditoria"] = st.session_state.notes_by_key.get(key, "")
            rechazadas.append(export_row)

    auditadas  = validadas + rechazadas
    pendientes = len(all_records) - len(auditadas)
    label_display = choice if choice != "— Todos —" else "Todas las fuentes"

    chips = ""
    if validadas:
        chips += f'<span class="chip-green">✓ {len(validadas)}</span>'
    if rechazadas:
        chips += f'<span class="chip-red">✗ {len(rechazadas)}</span>'
    if pendientes:
        chips += f'<span class="chip-gray">⏳ {pendientes}</span>'

    st.markdown(
        f"""
        <div class="export-panel">
          <div class="export-title">📥 Exportar interconsultas auditadas</div>
          <div class="export-row">
            <span class="export-fuente">{label_display}</span>
            <span class="export-chips">{chips}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if auditadas:
        slug = choice.lower().replace("— todos —", "todas").replace(" ", "_")
        fname = f"interconsultas_{slug}_auditadas.json"
        data  = json.dumps(auditadas, ensure_ascii=False, indent=2).encode("utf-8")
        st.download_button(
            label=f"⬇ Descargar JSON ({len(auditadas)} registros auditados)",
            data=data,
            file_name=fname,
            mime="application/json",
            use_container_width=True,
            key="dl_export",
        )
    else:
        st.caption("Valida o rechaza interconsultas para habilitar la descarga.")


def render_footer_bar(row: dict) -> None:
    prio_raw = row.get("PRIORIDAD_DESTINO")
    _, dot_cls, prio_text = priority_info(prio_raw)
    fecha_ic = fmt(row.get("FECHA_IC"))
    fecha_larga = fmt_fecha_larga(fecha_ic) if fecha_ic != "—" else "—"
    estado_admin = fmt(row.get("GESTION_INTERCONSULTA"))

    st.markdown(
        f"""
        <div class="footer-bar">
          <div class="footer-item">
            <span>
              <span class="footer-label">Prioridad de Atención</span>
              <span class="footer-val">
                <span class="prio-dot {dot_cls}"></span>{prio_text}
              </span>
            </span>
          </div>
          <div style="width:1px;background:#e5e7eb;height:28px;"></div>
          <div class="footer-item">
            <span>
              <span class="footer-label">Fecha de Emisión IC</span>
              <span class="footer-val">📅 {fecha_larga}</span>
            </span>
          </div>
          <div style="width:1px;background:#e5e7eb;height:28px;"></div>
          <div class="footer-item">
            <span>
              <span class="footer-label">Estado Administrativo</span>
              <span class="footer-val">{estado_admin}</span>
            </span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(
        page_title="Panel Interconsultas",
        page_icon="🏥",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_styles()
    ensure_session_defaults()

    # Mostrar modal de confirmación si hay una decisión pendiente
    pc = st.session_state.pending_confirm
    if pc:
        modal_confirmacion(pc["key"], pc["accion"], pc["nota"])

    # ── Cargar fuentes desde la API ───────────────────────────────────────────
    fuentes = api_get_files()
    if not fuentes:
        st.error("No hay datos disponibles. Verifica que la API esté corriendo.")
        st.stop()

    # Reclamos activos (compartidos entre todos los usuarios)
    claims = api_get_claims()

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(
            """
            <div class="sb-brand">
              <span class="sb-dot"></span>
              <div>
                <div class="sb-title">DocRef Dashboard</div>
                <div class="sb-sub">Panel de Auditoría Clínica</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.divider()

        # ── Identificación de sesión (automática) ────────────────────────────
        st.caption(f"Sesión: `{st.session_state.auditor_name}`")

        st.divider()

        file_options = ["— Todos —"] + [fuente_display(f) for f in fuentes]
        choice = st.selectbox("Fuente de datos", options=file_options, index=0)
        if st.session_state.get("last_choice") != choice:
            st.session_state.last_choice = choice
            st.session_state.selected_key = None
            # Liberar reclamo anterior al cambiar de fuente
            if st.session_state.claimed_key:
                api_release_claim(st.session_state.claimed_key)
                st.session_state.claimed_key = None

        records = load_records(choice)
        if not records:
            st.warning("Sin datos para esta fuente.")
            st.stop()

        labels: dict = {}  # sin labels locales; el estado viene de _validado en cada row
        counts = count_by_status(records, labels)

        search = st.text_input(
            "Buscar",
            placeholder="Diagnóstico, establecimiento…",
            key="filter_search",
        )

        st.markdown("**Bandeja**")
        estado = st.radio(
            "bandeja",
            options=["Pendientes", "Validadas", "Invalidadas", "Todos"],
            label_visibility="collapsed",
            key="estado_radio",
        )
        st.markdown(
            f"""
            <div class="sb-item {'sb-item-active' if estado == 'Pendientes' else ''}">
              <span>Pendientes</span>
              <span class="sb-badge">{counts["Pendientes"]}</span>
            </div>
            <div style="height:.35rem"></div>
            <div class="sb-item {'sb-item-active' if estado == 'Validadas' else ''}">
              <span>Validadas</span>
              <span style="color:#94a3b8 !important;font-weight:700;">{counts["Validadas"]}</span>
            </div>
            <div style="height:.35rem"></div>
            <div class="sb-item {'sb-item-active' if estado == 'Invalidadas' else ''}">
              <span>Invalidadas</span>
              <span style="color:#94a3b8 !important;font-weight:700;">{counts["Invalidadas"]}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

        especies = sorted(
            {fmt(r.get("ESPECIALIDAD_DESTINO")) for r in records
             if fmt(r.get("ESPECIALIDAD_DESTINO")) != "—"}
        )
        espec_sel = st.selectbox("Especialidad destino", options=["Todos"] + especies)

        prios = sorted(
            {fmt(r.get("PRIORIDAD_DESTINO")) for r in records
             if fmt(r.get("PRIORIDAD_DESTINO")) != "—"}
        )
        prio_sel = st.selectbox("Prioridad", options=["Todos"] + prios)

        st.divider()

        # Botón de refresco manual
        if st.button("🔄 Actualizar datos", use_container_width=True):
            api_get_records.clear()
            api_get_all_records.clear()
            api_get_claims.clear()
            api_get_files.clear()
            st.rerun()

        st.caption("Sistema de interconsultas · DocRef")

    # ── Filtrar ───────────────────────────────────────────────────────────────
    filtered = filter_records(records, search, estado, espec_sel, prio_sel, labels)
    if not filtered:
        st.warning("No hay resultados con los filtros actuales.")
        st.stop()

    keys_order = [k for k, _ in filtered]
    lookup = {k: r for k, r in filtered}

    if st.session_state.selected_key is None or st.session_state.selected_key not in keys_order:
        st.session_state.selected_key = keys_order[0]

    active_key = st.session_state.selected_key
    if active_key not in lookup:
        active_key = keys_order[0]
        st.session_state.selected_key = active_key
    active_row = lookup[active_key]
    st_lbl = row_status(active_row, active_key, labels)

    # ── Claim automático al abrir un registro ─────────────────────────────────
    auditor_name = st.session_state.auditor_name
    prev_claimed = st.session_state.claimed_key

    if active_key != prev_claimed:
        # Liberar el reclamo anterior
        if prev_claimed:
            api_release_claim(prev_claimed)
        # Intentar reclamar el nuevo
        ok, err = api_claim(active_key, auditor_name)
        if ok:
            st.session_state.claimed_key = active_key
            st.session_state.claim_error = ""
            claims = api_get_claims()  # refrescar para mostrar badge correcto
        else:
            st.session_state.claimed_key = None
            st.session_state.claim_error = err

    # ── Top bar ───────────────────────────────────────────────────────────────
    if st_lbl == "validada":
        status_cls, status_txt = "status-valid", "AUDITADA"
    elif st_lbl == "invalidada":
        status_cls, status_txt = "status-invalid", "RECHAZADA"
    else:
        status_cls, status_txt = "status-pending", "PENDIENTE AUDICIÓN"

    st.markdown(
        f"""
        <div class="topbar">
          <div class="topbar-left">
            <span class="ic-pill">IC #{fmt(active_row.get("NUM_INTERCONSULTA"))}</span>
            <span class="page-title">Expediente de Interconsulta</span>
          </div>
          <span class="status-pill {status_cls}">{status_txt}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Mostrar error de claim si existe
    if st.session_state.claim_error:
        st.warning(f"⚠ {st.session_state.claim_error}")

    # ── Layout principal: izquierda (lista) + derecha (detalle) ──────────────
    col_list, col_detail = st.columns([0.32, 0.68], gap="medium")

    # ── Columna izquierda: listado ────────────────────────────────────────────
    with col_list:
        st.markdown(
            f'<p class="list-head">LISTADO DE REGISTROS</p>'
            f'<p class="dash-muted" style="margin-bottom:.6rem;">'
            f'{len(filtered)} registro{"s" if len(filtered) != 1 else ""}</p>',
            unsafe_allow_html=True,
        )
        for key, row in filtered:
            render_list_card(key, row, key == active_key, labels, claims)

    # ── Columna derecha: detalle ──────────────────────────────────────────────
    with col_detail:
        render_info_strip(active_row)
        st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)

        c_hist, c_req = st.columns([1.55, 1.0], gap="medium")

        with c_hist:
            render_historia(active_row, active_key)

        with c_req:
            render_requerimientos(active_row)
            render_examenes(active_row, active_key)
            st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)
            render_panel_resolucion(active_key, active_row, labels, claims)

        render_footer_bar(active_row)

        st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)
        render_export_panel(records, choice, labels)

        with st.expander("Ver todos los campos (JSON)", expanded=False):
            st.json(active_row)

    # ── Auto-refresco: indicador de actividad compartida ─────────────────────
    # El fragment se re-ejecuta cada 30 s de forma independiente al resto de la
    # página, mostrando cuántos reclamos activos hay en tiempo real.
    @st.fragment(run_every=30)
    def live_claims_indicator() -> None:
        api_get_claims.clear()
        current_claims = api_get_claims()
        n = len(current_claims)
        if n:
            auditores = ", ".join(sorted(set(current_claims.values())))
            st.caption(f"🟢 {n} auditor{'es' if n > 1 else ''} activo{'s' if n > 1 else ''}: {auditores}")
        else:
            st.caption("Sin auditores activos en este momento.")

    live_claims_indicator()


if __name__ == "__main__":
    main()
