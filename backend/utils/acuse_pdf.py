from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import weasyprint
from sqlalchemy.orm import Session

from backend.core.templates import templates
from backend.core.config_institucional import get_configuracion_institucional
from backend.database.models.CatUnidadAcademica import CatUnidadAcademica

TEXTO_ACUSE_DEFAULT = (
    'Con esta fecha, se notifica de la conclusión de la captura de la información requerida '
    'a traves del "Sistema de Captura y Análisis de la Estadística (SICAE)", para el Proceso de '
    'Estadística Básica Institucional, de la que se acusa de recibido con el número de folio '
    'asignado en este documento. A partir de este momento, la Dirección de Información Institucional '
    'dará inicio a la revisión de su información.'
)


def _fecha_es_larga(dt: datetime) -> str:
    meses = [
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    ]
    return f"{dt.day} de {meses[dt.month - 1]} del {dt.year}"


def generar_oficio_conclusion_pdf_en_memoria(
    *,
    escuela: str,
    sigla: str,
    folio: str,
    clave_ur: Optional[str] = None,
    fecha_documento: Optional[datetime] = None,
    fecha_evento: Optional[datetime] = None,
    texto_cuerpo: Optional[str] = None,
    estatus_entrega: Optional[str] = None,
    db: Optional[Session] = None,
    config_override: Optional[Dict[str, Any]] = None,
) -> bytes:
    """
    Genera el Oficio Institucional Oficial de Conclusión de Captura (IPN / SEP)
    en formato horizontal (Carta Landscape) usando WeasyPrint y la plantilla oficial.
    """
    now = fecha_documento or datetime.now()
    cfg = get_configuracion_institucional()
    if config_override:
        cfg.update(config_override)

    # 1. Consultar clave_ur real y nombre oficial desde CatUnidadAcademica
    clave_ur_final = (str(clave_ur).strip() if clave_ur else None)
    nombre_oficial_ua = escuela
    sigla_final = sigla

    if not clave_ur_final or not nombre_oficial_ua or not sigla_final:
        local_db = db
        should_close = False
        if local_db is None:
            try:
                from backend.database.connection import SessionLocal
                local_db = SessionLocal()
                should_close = True
            except Exception:
                local_db = None

        if local_db is not None:
            try:
                busqueda_sigla = (sigla or "").strip()
                busqueda_escuela = (escuela or "").strip()
                
                ua_db = local_db.query(CatUnidadAcademica).filter(
                    (CatUnidadAcademica.Sigla.ilike(busqueda_sigla)) |
                    (CatUnidadAcademica.Nombre.ilike(busqueda_escuela)) |
                    (CatUnidadAcademica.Sigla.ilike(busqueda_escuela)) |
                    (CatUnidadAcademica.Nombre.ilike(f"%{busqueda_sigla}%"))
                ).first()
                
                if ua_db:
                    if not clave_ur_final and ua_db.Clave:
                        clave_ur_final = str(ua_db.Clave).strip()
                    if ua_db.Nombre:
                        nombre_oficial_ua = str(ua_db.Nombre).strip()
                    if ua_db.Sigla:
                        sigla_final = str(ua_db.Sigla).strip()
            except Exception as e:
                print(f"⚠️ Error al consultar CatUnidadAcademica en acuse_pdf: {e}")
            finally:
                if should_close and local_db:
                    local_db.close()

    clave_ur_final = clave_ur_final or "O3A000"

    # 2. Formatear nombre completo con siglas
    if sigla_final and sigla_final.upper() not in nombre_oficial_ua.upper():
        nombre_completo_ua = f"{nombre_oficial_ua} ({sigla_final})"
    else:
        nombre_completo_ua = nombre_oficial_ua

    # 3. Rutas de imágenes
    repo_root = Path(__file__).resolve().parents[2]
    static_base = repo_root / "frontend" / "static"
    logos_dir = static_base / "logos" / "institucional"

    logo_sep_ipn_path = (logos_dir / cfg.get("logo_sep_ipn", "logo_sep_ipn.png")).as_uri()
    heroina_header_path = (logos_dir / cfg.get("imagen_heroina_header", "heroina_bandera.png")).as_uri()
    personaje_footer_path = (logos_dir / cfg.get("imagen_personaje_footer", "margarita_maza_2026.png")).as_uri()

    # 4. Textos y fechas
    fecha_larga = _fecha_es_larga(now)
    hora_str = now.strftime("%H:%M:%S")
    texto_oficial_final = texto_cuerpo or cfg.get("texto_oficial", TEXTO_ACUSE_DEFAULT)

    # Detectar si es entrega extemporánea
    es_extemporaneo = bool(
        estatus_entrega and "extempor" in str(estatus_entrega).strip().lower()
    )

    contexto = {
        "folio": folio,
        "clave_ur": clave_ur_final,
        "fecha_larga": fecha_larga,
        "hora": hora_str,
        "sigla_unidad": sigla_final,
        "unidad_nombre": nombre_completo_ua,
        "texto_oficial": texto_oficial_final,
        "titulo_proceso": cfg.get("titulo_proceso", "PROCESO DE ESTADISTICA BASICA INSTITUCIONAL"),
        "dependencias": cfg.get("dependencias_encabezado", []),
        "aniversarios": cfg.get("aniversarios", []),
        "pie_pagina": cfg.get("pie_pagina", {}),
        "firmante": cfg.get("firmante", {}),
        "logo_sep_ipn_url": logo_sep_ipn_path,
        "heroina_header_url": heroina_header_path,
        "personaje_footer_url": personaje_footer_path,
        "es_extemporaneo": es_extemporaneo,
    }

    html_rendered = templates.get_template("oficio_conclusion_captura.html").render(contexto)

    pdf_bytes = weasyprint.HTML(
        string=html_rendered,
        base_url=str(static_base)
    ).write_pdf()

    return pdf_bytes


def generar_acuse_matricula_pdf_en_memoria(
    *,
    escuela: str,
    sigla: str,
    folio: str,
    clave_ur: Optional[str] = None,
    fecha_documento: Optional[datetime] = None,
    fecha_evento: Optional[datetime] = None,
    texto_cuerpo: Optional[str] = None,
    estatus_entrega: Optional[str] = None,
    db: Optional[Session] = None,
    **kwargs,
) -> bytes:
    """Wrapper compatible para generar el acuse oficial de conclusión horizontal."""
    return generar_oficio_conclusion_pdf_en_memoria(
        escuela=escuela,
        sigla=sigla,
        folio=folio,
        clave_ur=clave_ur,
        fecha_documento=fecha_documento,
        fecha_evento=fecha_evento,
        texto_cuerpo=texto_cuerpo,
        estatus_entrega=estatus_entrega,
        db=db,
    )


def generar_acuse_matricula_pdf(
    *,
    escuela: str,
    sigla: str,
    folio: str,
    output_path: str | Path,
    clave_ur: Optional[str] = None,
    fecha_documento: Optional[datetime] = None,
    fecha_evento: Optional[datetime] = None,
    texto_cuerpo: Optional[str] = None,
    db: Optional[Session] = None,
    **kwargs,
) -> Path:
    """Genera el oficio de conclusión y lo guarda en disco en output_path."""
    pdf_bytes = generar_acuse_matricula_pdf_en_memoria(
        escuela=escuela,
        sigla=sigla,
        folio=folio,
        clave_ur=clave_ur,
        fecha_documento=fecha_documento,
        fecha_evento=fecha_evento,
        texto_cuerpo=texto_cuerpo,
        db=db,
    )
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(pdf_bytes)
    return out_path
