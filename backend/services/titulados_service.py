from operator import ge
from sqlalchemy.orm import Session
from backend.crud.ConsultaTitulados import get_titulados
#from backend.schemas.titulados import TituladoSchema
from typing import List, Dict, Any
from backend.database.connection import get_db
from backend.database.models.Temp_Titulados import Temp_Titulados

def obtener_titulados(
    db: Session,
    unidad_academica,
    periodo,
    nivel,
    usuario,
    host
) :
    """
    Capa de servicio: valida parámetros y llama al crud.
    Aquí puedes agregar lógica adicional, filtros, transformaciones, etc.
    """
    if not unidad_academica or not periodo or not nivel or not usuario:
        raise ValueError("Todos los parámetros son obligatorios.")

    datos = get_titulados(
        db=db,
        unidad_academica=unidad_academica,
        periodo=periodo,
        nivel=nivel,
        usuario=usuario,
        host=host
    )

    if datos:

        contexto = {
            "Periodo" : datos[0].get("Periodo"),
            "Sigla" : datos[0].get("Sigla"),
            "Boleta" : datos[0].get("Boleta"),
        }

        filas = [{
            "Nombre_Programa": row["Nombre_Programa"],
            "Nombre_Rama": row["Nombre_Rama"],
            "Nivel": row["Nivel"],
            "Modalidad": row["Modalidad"],
            "Grupo_Edad": row["Grupo_Edad"],
            "Tipo_Titulacion": row["Tipo_Titulacion"],
            "Turno": row["Turno"],
            "Sexo": row["Sexo"],
            "Id_Semaforo": row["Id_Semaforo"],
            "Titulados": row["Titulados"],
        }
        for row in datos
        ]
    else:
        contexto = {}
        filas = []

    return contexto, filas

def limpiar_numero(val):
                if val == '' or val is None:
                    return 0
                return int(val)

def preparar_datos_temp_titulados(
    datos: List[Dict[str, Any]],
    periodo: str,
    sigla: str,
    nivel: str,
) -> List[Temp_Titulados]:
    
    registros = []

    for fila in datos:
        base = {
            "Periodo": periodo,
            "Sigla": sigla,
            "Nombre_Programa": fila.get("programaNombre", ""),
            "Nombre_Rama": fila.get("ramaNombre", ""),
            "Nivel": nivel,
            "Modalidad": fila.get("modalidadNombre", ""),
            "Grupo_Edad": fila.get("edadNombre", ""),
            "Boleta": int(fila["boletaNombre"]) if str(fila.get("boletaNombre", "")).isdigit() else 0,
            "Tipo_Titulacion": fila.get("generacionNombre", ""),
            "Turno": fila.get("turnoNombre", ""),
        }

        registros.append(Temp_Titulados(
            **base,
            Sexo="Hombre",
            Titulados=limpiar_numero(fila.get("hombres")),
        ))

        registros.append(Temp_Titulados(
            **base,
            Sexo="Mujer",
            Titulados=limpiar_numero(fila.get("mujeres")),
        ))

    return registros
          
    
    
if __name__ == "__main__":
    with next(get_db()) as db:
        contexto, filas = obtener_titulados(
            db=db,
            unidad_academica='ESIME Zacatenco',
            periodo='2025-2026/2',
            nivel='Superior',
            usuario='admin',
            host='Test'
        )
        print(f"Contexto: {contexto}")
        for fila in range(min(106, len(filas))):
            print(f"Fila {fila + 1}: {filas[fila]}")
        #print(f"Filas: {filas}")
