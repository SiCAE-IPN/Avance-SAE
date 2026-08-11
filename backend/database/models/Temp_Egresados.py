from ..db_base import Base
from sqlalchemy import Integer, ForeignKey, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

class Temp_Egresados(Base):
    __tablename__ = 'Temp_Egresados'

    Periodo: Mapped[str] = mapped_column(String(50), primary_key=True, index=True, nullable=False)
    Sigla: Mapped[str] = mapped_column(String(50), primary_key=True, index=True, nullable=False)
    Nombre_Programa: Mapped[str] = mapped_column(String(100), primary_key=True, nullable=False)
    Nombre_Rama: Mapped[str] = mapped_column(String(50), nullable=False) # Este puede quedar normal o ser PK
    Nivel: Mapped[str] = mapped_column(String(50), nullable=False)
    Modalidad: Mapped[str] = mapped_column(String(50), primary_key=True, nullable=False)
    Grupo_Edad: Mapped[str] = mapped_column(String(50), primary_key=True, nullable=False)
    Boleta: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    Generacion: Mapped[str] = mapped_column(String(50), primary_key=True, nullable=False)
    Turno: Mapped[str] = mapped_column(String(50), primary_key=True, nullable=False)
    Sexo: Mapped[str] = mapped_column(String(50), primary_key=True, nullable=False)
    Id_Semaforo: Mapped[int] = mapped_column(nullable=False)
    Egresados: Mapped[int] = mapped_column(nullable=True)    