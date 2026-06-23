from backend.schemas import Boleta
from ..db_base import Base
from sqlalchemy import Integer, ForeignKey, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime 

class Temp_Titulados(Base):
    __tablename__ = 'Temp_Titulados'
    
    Periodo:        Mapped[str] = mapped_column(String(50), primary_key=True, nullable=False)
    Sigla:          Mapped[str] = mapped_column(String(50), primary_key=True, nullable=False)
    Nombre_Programa:Mapped[str] = mapped_column(String(100), primary_key=True, nullable=False)
    Nombre_Rama:    Mapped[str] = mapped_column(String(50), primary_key=True, nullable=False)
    Nivel:          Mapped[str] = mapped_column(String(50), primary_key=True, nullable=False)
    Modalidad:      Mapped[str] = mapped_column(String(50), primary_key=True, nullable=False)
    Grupo_Edad:     Mapped[str] = mapped_column(String(50), primary_key=True, nullable=False)
    Boleta:         Mapped[int] = mapped_column(primary_key=True, nullable=False)
    Tipo_Titulacion:Mapped[str] = mapped_column(String(50), primary_key=True, nullable=False)
    Turno:          Mapped[str] = mapped_column(String(50), primary_key=True, nullable=False)
    Sexo:           Mapped[str] = mapped_column(String(50), primary_key=True, nullable=False)
    Titulados:      Mapped[int] = mapped_column(nullable=True)