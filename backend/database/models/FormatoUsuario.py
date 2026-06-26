from __future__ import annotations

from ..db_base import Base
from sqlalchemy import String, Integer, DateTime, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from typing import Optional

class Usuario(Base):
    __tablename__ = "Formato_Usuario"

    Id_Formato: Mapped[int] = mapped_column(primary_key=True, index=True)
    Id_Usuario: Mapped[int] = mapped_column(Integer, ForeignKey("Usuarios.Id_Usuario"), nullable=False)
    Fecha_Inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    Fecha_Modificacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    Fecha_Final: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    Id_Estatus: Mapped[int] = mapped_column(Integer, ForeignKey("Cat_Estatus.Id_Estatus"), nullable=False)