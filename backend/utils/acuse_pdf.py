from __future__ import annotations

from datetime import datetime
from pathlib import Path
from io import BytesIO

from reportlab.lib.pagesizes import landscape
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas


TEXTO_ACUSE_DEFAULT = (
    'Con esta fecha, se notifica de la conclusión de la captura de la información requerida'
    'a traves del "Sistema de Captura y Análisis de la Estadística (SICAE)",'
    'para el Proceso de Estadística Básica Institucional, de la que se acusa de recibido con el número'
    'de folio asignado en este documento. A partir de este momento, la Dirección de Información,'
    'dará inicio a la revisión de su información.'
)

FONT_REGULAR = "NotoSans-Regular"
FONT_BOLD = "NotoSans-Bold"
_FONTS_REGISTERED = False


def _get_font_candidates() -> list[tuple[Path, Path]]:
    this_file = Path(__file__).resolve()
    repo_root = this_file.parents[2]

    candidates = [
        (
            repo_root / "frontend" / "static" / "fonts" / "NotoSans-Regular.ttf",
            repo_root / "frontend" / "static" / "fonts" / "NotoSans-Bold.ttf",
        ),
        (
            repo_root / "backend" / "assets" / "fonts" / "NotoSans-Regular.ttf",
            repo_root / "backend" / "assets" / "fonts" / "NotoSans-Bold.ttf",
        ),
    ]
    return candidates


def _register_noto_fonts() -> None:
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return

    for regular_path, bold_path in _get_font_candidates():
        if regular_path.exists() and bold_path.exists():
            pdfmetrics.registerFont(TTFont(FONT_REGULAR, str(regular_path)))
            pdfmetrics.registerFont(TTFont(FONT_BOLD, str(bold_path)))
            _FONTS_REGISTERED = True
            return

    expected = "frontend/static/fonts/NotoSans-Regular.ttf y frontend/static/fonts/NotoSans-Bold.ttf"
    raise FileNotFoundError(
        "No se encontraron las fuentes NotoSans obligatorias. "
        f"Coloca los archivos en: {expected}."
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


def _wrap_text_for_canvas(
    canvas: Canvas,
    text: str,
    font_name: str,
    font_size: int,
    max_width: float,
) -> list[str]:
    words = text.split()
    if not words:
        return []

    lines: list[str] = []
    current_words: list[str] = []

    for word in words:
        candidate = " ".join([*current_words, word])
        if canvas.stringWidth(candidate, font_name, font_size) <= max_width:
            current_words.append(word)
            continue

        if current_words:
            lines.append(" ".join(current_words))
        current_words = [word]

    if current_words:
        lines.append(" ".join(current_words))

    return lines


def generar_acuse_matricula_pdf(
    *,
    escuela: str,
    sigla: str,
    folio: str,
    output_path: str | Path,
    fecha_documento: datetime | None = None,
    fecha_evento: datetime | None = None,
    clave_ur: str = "O3A000",
    texto_cuerpo: str = TEXTO_ACUSE_DEFAULT,
    firmante: str = "MTRO. ORLANDO DAVID PARADA VICENTE",
    cargo_firmante: str = "COORDINADOR GENERAL DE PLANEACION E INFORMACION INSTITUCIONAL",
    lema: str = '"La Tecnica al Servicio de la Patria"',
) -> Path:
    """Genera un acuse en PDF con formato horizontal tipo oficio.

    Esta funcion no consulta base de datos: recibe los datos ya resueltos por el modulo
    que la invoque para mantenerla reutilizable.
    """
    _register_noto_fonts()

    now = fecha_documento or datetime.now()
    evento = fecha_evento or now

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    width, height = landscape((21.59 * cm, 27.94 * cm))
    canvas = Canvas(str(out_path), pagesize=(width, height))

    # Encabezado de fecha y hora
    fecha_actual = _fecha_es_larga(now)
    hora_actual = now.strftime("%H:%M:%S")

    canvas.setFont(FONT_REGULAR, 11)
    canvas.drawString(2 * cm, height - 2 * cm, f"Ciudad de Mexico, a {fecha_actual}")
    canvas.drawString(2 * cm, height - 2.7 * cm, f"Hora: {hora_actual}")

    # Datos de folio y clave
    canvas.drawString(2 * cm, height - 3.8 * cm, f"Clave UR: {clave_ur}")
    canvas.drawString(2 * cm, height - 4.5 * cm, f"Folio: {folio}")

    # Destinatario
    canvas.setFont(FONT_BOLD, 12)
    canvas.drawString(2 * cm, height - 6 * cm, f"{escuela} ({sigla})")
    canvas.drawString(2 * cm, height - 6.8 * cm, "INSTITUTO POLITECNICO NACIONAL")
    canvas.drawString(2 * cm, height - 7.6 * cm, "PRESENTE")

    # Titulo
    canvas.setFont(FONT_BOLD, 13)
    canvas.drawCentredString(width / 2, height - 9 * cm, "PROCESO DE ESTADISTICA BASICA INSTITUCIONAL")

    # Cuerpo principal con ajuste de linea
    canvas.setFont(FONT_REGULAR, 12)
    max_text_width = width - (4 * cm)
    body_lines = _wrap_text_for_canvas(canvas, texto_cuerpo, FONT_REGULAR, 12, max_text_width)

    text_object = canvas.beginText(2 * cm, height - 10 * cm)
    text_object.setLeading(16)
    for line in body_lines:
        text_object.textLine(line)
    canvas.drawText(text_object)

    # Pie institucional
    canvas.setFont(FONT_BOLD, 12)
    canvas.drawCentredString(width / 2, 4.5 * cm, lema)

    canvas.line(width / 2 - 4 * cm, 3.2 * cm, width / 2 + 4 * cm, 3.2 * cm)

    canvas.drawCentredString(width / 2, 2.5 * cm, firmante)
    canvas.setFont(FONT_BOLD, 11)
    canvas.drawCentredString(width / 2, 1.8 * cm, cargo_firmante)

    # Metadatos de referencia para trazabilidad
    canvas.setAuthor("SiCAE")
    canvas.setTitle(f"Acuse de Matricula - {sigla}")
    canvas.setSubject(f"Evento de captura/validacion del {evento.strftime('%d/%m/%Y %H:%M:%S')}")

    canvas.save()
    return out_path


def generar_acuse_matricula_pdf_en_memoria(
    *,
    escuela: str,
    sigla: str,
    folio: str,
    fecha_documento: datetime | None = None,
    fecha_evento: datetime | None = None,
    clave_ur: str = "O3A000",
    texto_cuerpo: str = TEXTO_ACUSE_DEFAULT,
    firmante: str = "MTRO. ORLANDO DAVID PARADA VICENTE",
    cargo_firmante: str = "COORDINADOR GENERAL DE PLANEACION E INFORMACION INSTITUCIONAL",
    lema: str = '"La Tecnica al Servicio de la Patria"',
) -> bytes:
    """Genera el acuse en memoria y devuelve el PDF en bytes (ideal para respuestas HTTP)."""
    _register_noto_fonts()

    buffer = BytesIO()
    now = fecha_documento or datetime.now()
    evento = fecha_evento or now

    width, height = landscape((21.59 * cm, 27.94 * cm))
    canvas = Canvas(buffer, pagesize=(width, height))

    fecha_actual = _fecha_es_larga(now)
    hora_actual = now.strftime("%H:%M:%S")

    canvas.setFont(FONT_REGULAR, 11)
    canvas.drawString(2 * cm, height - 2 * cm, f"Ciudad de Mexico, a {fecha_actual}")
    canvas.drawString(2 * cm, height - 2.7 * cm, f"Hora: {hora_actual}")

    canvas.drawString(2 * cm, height - 3.8 * cm, f"Clave UR: {clave_ur}")
    canvas.drawString(2 * cm, height - 4.5 * cm, f"Folio: {folio}")

    canvas.setFont(FONT_BOLD, 12)
    canvas.drawString(2 * cm, height - 6 * cm, f"{escuela} ({sigla})")
    canvas.drawString(2 * cm, height - 6.8 * cm, "INSTITUTO POLITECNICO NACIONAL")
    canvas.drawString(2 * cm, height - 7.6 * cm, "PRESENTE")

    canvas.setFont(FONT_BOLD, 13)
    canvas.drawCentredString(width / 2, height - 9 * cm, "PROCESO DE ESTADISTICA BASICA INSTITUCIONAL")

    canvas.setFont(FONT_REGULAR, 12)
    max_text_width = width - (4 * cm)
    body_lines = _wrap_text_for_canvas(canvas, texto_cuerpo, FONT_REGULAR, 12, max_text_width)

    text_object = canvas.beginText(2 * cm, height - 10 * cm)
    text_object.setLeading(16)
    for line in body_lines:
        text_object.textLine(line)
    canvas.drawText(text_object)

    canvas.setFont(FONT_BOLD, 12)
    canvas.drawCentredString(width / 2, 4.5 * cm, lema)

    canvas.line(width / 2 - 4 * cm, 3.2 * cm, width / 2 + 4 * cm, 3.2 * cm)

    canvas.drawCentredString(width / 2, 2.5 * cm, firmante)
    canvas.setFont(FONT_BOLD, 11)
    canvas.drawCentredString(width / 2, 1.8 * cm, cargo_firmante)

    canvas.setAuthor("SiCAE")
    canvas.setTitle(f"Acuse de Matricula - {sigla}")
    canvas.setSubject(f"Evento de captura/validacion del {evento.strftime('%d/%m/%Y %H:%M:%S')}")

    canvas.save()
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
