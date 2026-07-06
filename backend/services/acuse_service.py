from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.core.templates import BASE_DIR


@dataclass(frozen=True)
class AcuseGenerado:
    folio: str
    file_name: str
    file_path: Path
    relative_url: str


def _safe_slug(text: str) -> str:
    raw = (text or "").strip().lower()
    slug = re.sub(r"[^a-z0-9_-]+", "-", raw)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "na"


def get_acuses_root_dir() -> Path:
    root = Path(BASE_DIR) / "backend" / "storage" / "acuses"
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_user_acuses_dir(usuario_login: str) -> Path:
    user_dir = get_acuses_root_dir() / _safe_slug(usuario_login)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def build_folio_acuse(*, periodo_literal: str, unidad_sigla: str, estatus_entrega: str | None = None) -> str:
    sufijo = "ORDINARIA"
    if estatus_entrega and "extempor" in estatus_entrega.strip().lower():
        sufijo = "EXTEMPORANEA"
    return f"{_safe_slug(unidad_sigla).upper()}-{_safe_slug(periodo_literal).upper()}"


def save_acuse_pdf_for_user(
    *,
    usuario_login: str,
    folio: str,
    periodo_literal: str,
    unidad_sigla: str,
    pdf_bytes: bytes,
) -> AcuseGenerado:
    user_dir = get_user_acuses_dir(usuario_login)
    file_name = (
        f"{_safe_slug(folio)}.pdf"
    )
    file_path = user_dir / file_name
    file_path.write_bytes(pdf_bytes)

    relative_url = f"/matricula/acuses/download/{file_name}"
    return AcuseGenerado(
        folio=folio,
        file_name=file_name,
        file_path=file_path,
        relative_url=relative_url,
    )


def get_user_acuse_file(usuario_login: str, file_name: str) -> Path | None:
    safe_name = Path(file_name).name
    if not safe_name.lower().endswith(".pdf"):
        return None

    candidate = get_user_acuses_dir(usuario_login) / safe_name
    if not candidate.exists() or not candidate.is_file():
        return None
    return candidate


def list_user_acuses(usuario_login: str) -> list[dict[str, Any]]:
    user_dir = get_user_acuses_dir(usuario_login)
    items: list[dict[str, Any]] = []

    for file_path in user_dir.glob("*.pdf"):
        stat = file_path.stat()
        created_at = datetime.fromtimestamp(stat.st_mtime)
        items.append(
            {
                "file_name": file_path.name,
                "download_url": f"/matricula/acuses/download/{file_path.name}",
                "created_at": created_at.isoformat(),
                "created_at_display": created_at.strftime("%d/%m/%Y %H:%M:%S"),
                "size_kb": round(stat.st_size / 1024, 2),
            }
        )

    items.sort(key=lambda x: x["created_at"], reverse=True)
    return items
