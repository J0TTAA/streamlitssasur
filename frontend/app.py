"""
Panel de auditoría clínica — Frontend Docker.
Consume la API REST (PostgreSQL-backed); sin autenticación.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Optional

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}


# ── API helpers ───────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False, ttl=300)
def fetch_files() -> list[str]:
    r = requests.get(f"{API_URL}/api/files", timeout=10)
    r.raise_for_status()
    return r.json()


@st.cache_data(show_spinner=False, ttl=600)
def fetch_records(fuente: str) -> list[dict]:
    r = requests.get(f"{API_URL}/api/records/{fuente}", timeout=60)
    r.raise_for_status()
    return r.json()


def _api_get_labels() -> dict:
    r = requests.get(f"{API_URL}/api/labels", timeout=10)
    r.raise_for_status()
    return r.json()


def _api_set_label(key: str, status: str, note: str) -> None:
    requests.put(
        f"{API_URL}/api/labels/{key}",
        json={"status": status, "note": note},
        timeout=10,
    )


def _api_delete_label(key: str) -> None:
    requests.delete(f"{API_URL}/api/labels/{key}", timeout=10)


@st.cache_data(show_spinner=False, ttl=30)
def fetch_export_stats() -> list[dict]:
    r = requests.get(f"{API_URL}/api/export-stats", timeout=10)
    r.raise_for_status()
    return r.json()


def fetch_export_fuente(fuente: str) -> bytes:
    """Descarga los registros auditados de una fuente como JSON bytes."""
    r = requests.get(f"{API_URL}/api/export/{fuente}", timeout=30)
    r.raise_for_status()
    records = r.json()
    return json.dumps(records, ensure_ascii=False, indent=2).encode("utf-8")


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

        /* Ocultar la navegación automática de Streamlit */
        [data-testid="stSidebarNav"],
        [data-testid="stSidebarNavItems"],
        [data-testid="stSidebarNavSeparator"] { display: none !important; }

        /* Texto general del sidebar */
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

        /* Inputs y selectbox */
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

        /* ── Info strip ── */
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
        .info-section-sep { border-top:1px solid #f1f5f9; margin:.4rem 0; }
        .info-type-tag { font-size:.7rem; color:#6b7280; font-weight:500;
            text-transform:uppercase; letter-spacing:.04em; }
        .info-esp-tag { font-size:.78rem; font-weight:800; color:#b91c1c;
            text-transform:uppercase; letter-spacing:.01em; }

        /* ── Tarjetas listado ── */
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

        /* ── Secciones ── */
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
        .cie-label { font-size:.7rem; font-weight:700; color:#94a3b8;
            text-transform:uppercase; letter-spacing:.06em; }
        .diag-name {
            font-size:1.25rem; font-weight:900; color:#0f172a;
            letter-spacing:-.02em; margin:.15rem 0 .6rem;
        }
        .relato-label { font-size:.68rem; font-weight:800; color:#94a3b8;
            text-transform:uppercase; letter-spacing:.08em; margin-bottom:.35rem; }

        /* ── Requerimientos ── */
        .req-row {
            display:flex; align-items:flex-start; gap:.75rem;
            padding:.5rem 0; border-bottom:1px solid #f1f5f9;
        }
        .req-row:last-child { border-bottom:none; }
        .req-key { font-size:.7rem; font-weight:700; color:#9ca3af;
            text-transform:uppercase; letter-spacing:.07em;
            min-width:80px; padding-top:.05rem; }
        .req-val { font-size:.88rem; font-weight:600; color:#111827; }

        /* ── Exámenes ── */
        .exam-warn {
            background:#fffbeb; border:1px solid #fde68a; border-radius:8px;
            padding:.55rem .8rem; font-size:.8rem; color:#92400e;
        }

        /* ── Panel resolución ── */
        .panel-label { font-size:.68rem; font-weight:800; color:#9ca3af;
            text-transform:uppercase; letter-spacing:.08em; margin-bottom:.3rem; }

        /* ── Footer bar ── */
        .footer-bar {
            display:flex; align-items:center; gap:1.5rem;
            padding:.6rem .9rem; margin-top:.5rem;
            background:#fff; border:1px solid #e5e7eb; border-radius:10px;
            font-size:.8rem;
        }
        .footer-item { display:flex; align-items:center; gap:.45rem; color:#374151; }
        .footer-label { font-size:.65rem; font-weight:700; color:#9ca3af;
            text-transform:uppercase; letter-spacing:.06em; display:block; }
        .footer-val   { font-weight:700; color:#111827; }
        .prio-dot { width:8px; height:8px; border-radius:50%; display:inline-block; margin-right:.3rem; }
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


# ── Utilidades ────────────────────────────────────────────────────────────────

def fmt(val) -> str:
    if val is None:
        return "—"
    s = str(val).strip()
    return s if s else "—"


def short(s, n: int = 28) -> str:
    t = fmt(s)
    return t if (t == "—" or len(t) <= n) else t[:n] + "…"


def record_key(row: dict, fallback: str) -> str:
    n = row.get("NUM_INTERCONSULTA")
    i = row.get("ID")
    if n is not None:
        return str(n)
    if i is not None:
        return str(i)
    return fallback


def label_status(key: str, labels: dict) -> str:
    v = labels.get(key)
    if v == "valid":
        return "validada"
    if v == "invalid":
        return "invalidada"
    return "pendiente"


def ges_active(row: dict) -> bool:
    auge = fmt(row.get("ESTADO_AUGE"))
    prob = fmt(row.get("PROBLEMA_SALUD"))
    return "GES" in auge.upper() or (prob not in ("—", "NO TIENE") and len(prob) > 3)


def priority_info(raw) -> tuple[str, str, str]:
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
        s = label_status(key, labels)
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
        st_lbl = label_status(key, labels)
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


def ensure_session_defaults() -> None:
    st.session_state.setdefault("label_by_key", {})
    st.session_state.setdefault("notes_by_key", {})
    st.session_state.setdefault("selected_key", None)
    if not st.session_state.get("labels_loaded"):
        try:
            raw = _api_get_labels()
            for k, v in raw.items():
                st.session_state.label_by_key[k] = v["status"]
                if v.get("note"):
                    st.session_state.notes_by_key[k] = v["note"]
        except Exception:
            pass
        st.session_state.labels_loaded = True


# ── Componentes UI ────────────────────────────────────────────────────────────

def render_list_card(key: str, row: dict, selected: bool, labels: dict) -> None:
    st_lbl = label_status(key, labels)
    ges = ges_active(row)
    diag = fmt(row.get("NOM_DIAGNOSTICO"))
    diag_short = diag[:46] + ("…" if len(diag) > 46 else "")
    folio = fmt(row.get("NUM_INTERCONSULTA"))
    origen = short(row.get("ESTABLECIMIENTO_ORIGEN"), 22)
    fecha_raw = fmt(row.get("FECHA_IC"))
    fecha = fecha_raw.split(" ")[0] if fecha_raw != "—" else "—"

    if st_lbl == "validada":
        badge_html = '<span class="badge badge-green">Validada</span>'
    elif st_lbl == "invalidada":
        badge_html = '<span class="badge badge-red">Invalidada</span>'
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
          <div class="list-meta">📍 {origen}<br>🗓 {fecha}</div>
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
    col_a, col_b, col_c = st.columns([1.0, 1.1, 1.15], gap="small")

    with col_a:
        st.markdown(
            f"""
            <div class="info-box">
              <div class="info-label">Paciente</div>
              <div class="info-value">Edad: {fmt(row.get("EDAD_AÑOS"))} años</div>
              <div class="info-section-sep"></div>
              <div class="info-label">Previsión</div>
              <div class="info-value-link">{fmt(row.get("PREVISION_IC"))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_b:
        st.markdown(
            f"""
            <div class="info-box">
              <div class="info-label">Especialidad Origen</div>
              <div class="info-value">{fmt(row.get("ESTABLECIMIENTO_ORIGEN"))}</div>
              <div class="info-value-sm" style="margin-top:.2rem;">{fmt(row.get("ESPECIALIDAD_ORIGEN"))}</div>
              <div class="info-section-sep"></div>
              <div class="info-type-tag">{fmt(row.get("TIPO_DERIVACION"))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    dest_esp = fmt(row.get("GLOSA_ESP_DEIS_DEST")) or fmt(row.get("ESPECIALIDAD_DESTINO"))
    with col_c:
        st.markdown(
            f"""
            <div class="info-box">
              <div class="info-label">Especialidad / Policlínico</div>
              <div class="info-value">{fmt(row.get("ESTABLECIMIENTO_DESTINO"))}</div>
              <div class="info-section-sep"></div>
              <div class="info-esp-tag">{dest_esp} / {fmt(row.get("POLICLINICO_DESTINO"))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_historia(row: dict, key: str) -> None:
    ges = ges_active(row)
    ges_badge = (
        '<span class="badge badge-ges">GES / AUGE</span>' if ges
        else '<span class="badge badge-gray">NO GES / AUGE</span>'
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
          <div class="cie-label">Diagnóstico CIE-10:
            <code style="font-size:.72rem;color:#374151;">{cod}</code>
          </div>
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
    motivo = fmt(row.get("MOTIVO_INTERCONSULTA"))
    deriv  = fmt(row.get("DERIVADO_PARA"))
    req    = fmt(row.get("SE_REQUIERE"))

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


def render_panel_resolucion(key: str) -> None:
    st.markdown(
        """
        <div class="section-card" style="margin-bottom:.4rem;">
          <div class="section-title" style="margin-bottom:.15rem;">Panel de Resolución Médica</div>
          <div class="panel-label">Justificación clínica de la auditoría</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    note_key = f"note_input_{key}"
    if note_key not in st.session_state:
        st.session_state[note_key] = st.session_state.notes_by_key.get(key, "")

    new_note = st.text_area(
        "obs",
        key=note_key,
        height=120,
        placeholder="Ingrese las observaciones técnicas o motivos del rechazo/aprobación...",
        label_visibility="collapsed",
    )

    b1, b2 = st.columns(2, gap="small")
    with b1:
        if st.button("Validar pertinencia", type="primary",
                     use_container_width=True, key=f"v_ok_{key}"):
            st.session_state.label_by_key[key] = "valid"
            st.session_state.notes_by_key[key] = new_note
            try:
                _api_set_label(key, "valid", new_note)
            except Exception:
                pass
            st.rerun()
    with b2:
        if st.button("Rechazar solicitud", type="secondary",
                     use_container_width=True, key=f"v_bad_{key}"):
            st.session_state.label_by_key[key] = "invalid"
            st.session_state.notes_by_key[key] = new_note
            try:
                _api_set_label(key, "invalid", new_note)
            except Exception:
                pass
            st.rerun()

    if st.button("Volver a pendiente", use_container_width=True, key=f"v_pend_{key}"):
        st.session_state.label_by_key.pop(key, None)
        st.session_state.notes_by_key[key] = new_note
        try:
            _api_delete_label(key)
        except Exception:
            pass
        st.rerun()


def render_export_panel(all_fuentes: list[str]) -> None:
    """Panel de descarga de interconsultas auditadas, una por fuente."""
    try:
        stats = fetch_export_stats()
    except Exception:
        stats = []

    stats_map = {s["fuente"]: s for s in stats}
    total_auditadas = sum(
        s["validadas"] + s["rechazadas"] for s in stats
    )

    # Cabecera
    st.markdown(
        f"""
        <div class="export-panel">
          <div class="export-title">📥 Exportar interconsultas auditadas</div>
        """,
        unsafe_allow_html=True,
    )

    if total_auditadas == 0:
        st.markdown(
            '<p style="color:#9ca3af;font-size:.82rem;margin:.25rem 0 .75rem;">'
            'Aún no hay interconsultas auditadas para exportar.</p>',
            unsafe_allow_html=True,
        )
    else:
        for fuente in all_fuentes:
            s = stats_map.get(fuente, {})
            validadas  = s.get("validadas", 0)
            rechazadas = s.get("rechazadas", 0)
            pendientes = s.get("pendientes", 0)
            auditadas  = validadas + rechazadas

            # Nombre display: recortar prefijo largo
            display = fuente.replace("interconsultas_mg_", "").replace("_1000", "")

            chips = ""
            if validadas:
                chips += f'<span class="chip-green">✓ {validadas}</span>'
            if rechazadas:
                chips += f'<span class="chip-red">✗ {rechazadas}</span>'
            if pendientes:
                chips += f'<span class="chip-gray">⏳ {pendientes}</span>'

            st.markdown(
                f"""
                <div class="export-row">
                  <span class="export-fuente" title="{fuente}">{display}</span>
                  <span class="export-chips">{chips}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if auditadas > 0:
                try:
                    data = fetch_export_fuente(fuente)
                    filename = f"{fuente}_auditadas.json"
                    st.download_button(
                        label=f"⬇ Descargar JSON ({auditadas} registros)",
                        data=data,
                        file_name=filename,
                        mime="application/json",
                        use_container_width=True,
                        key=f"dl_{fuente}",
                    )
                except Exception as e:
                    st.caption(f"Error al preparar descarga: {e}")
            else:
                st.caption("Sin registros auditados aún.")

    st.markdown("</div>", unsafe_allow_html=True)


def render_footer_bar(row: dict) -> None:
    _, dot_cls, prio_text = priority_info(row.get("PRIORIDAD_DESTINO"))
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


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(
        page_title="Panel Interconsultas",
        page_icon="🏥",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_styles()

    try:
        files = fetch_files()
    except Exception as e:
        st.error(f"No se puede conectar a la API en `{API_URL}`. Error: {e}")
        st.stop()

    if not files:
        st.warning("No hay datos disponibles en la base de datos.")
        st.stop()

    ensure_session_defaults()

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

        choice = st.selectbox("Conjunto de datos", options=files, index=0)
        if st.session_state.get("last_fuente") != choice:
            st.session_state.last_fuente = choice
            st.session_state.selected_key = None

        with st.spinner("Cargando registros…"):
            try:
                records = fetch_records(choice)
            except Exception as e:
                st.error(f"Error al cargar registros: {e}")
                st.stop()

        if not records:
            st.warning("Sin registros en esta fuente.")
            st.stop()

        labels = st.session_state.label_by_key
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
        st.caption(f"API · {API_URL}")

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
    st_lbl = label_status(active_key, labels)

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

    # ── Layout: lista + detalle ───────────────────────────────────────────────
    col_list, col_detail = st.columns([0.32, 0.68], gap="medium")

    with col_list:
        st.markdown(
            f'<p class="list-head">LISTADO DE REGISTROS</p>'
            f'<p class="dash-muted" style="margin-bottom:.6rem;">'
            f'{len(filtered)} registro{"s" if len(filtered) != 1 else ""}</p>',
            unsafe_allow_html=True,
        )
        for key, row in filtered:
            render_list_card(key, row, key == active_key, labels)

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
            render_panel_resolucion(active_key)

        render_footer_bar(active_row)

        st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)
        render_export_panel(files)

        with st.expander("Ver todos los campos (JSON)", expanded=False):
            st.json(active_row)


if __name__ == "__main__":
    main()
