from operator import ge
from sqlalchemy.orm import Session
from backend.crud.ConsultaTitulados import get_titulados
#from backend.schemas.titulados import TituladoSchema
from typing import List, Dict, Any
from backend.database.connection import get_db
from backend.database.models.Temp_Titulados import Temp_Titulados
from collections import defaultdict

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
            "Boleta": row["Boleta"],
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

def limpiar_numero(valor: Any) -> int:
    # Si es None, una cadena vacía o solo espacios, devolvemos 0
    if valor is None or str(valor).strip() == "":
        return 0
    try:
        return int(float(valor)) # Convierte de forma segura strings o floats a int
    except (ValueError, TypeError):
        return 0



def preparar_datos_temp_titulados(
    datos: List[Dict[str, Any]],
    periodo: str,
    sigla: str,
    nivel: str,
) -> List[Temp_Titulados]:
    
    registros = []

    for fila in datos:
        # 1. Extraemos la base común para este registro (sin Turno ni Sexo)
        base_comun = {
            "Periodo": periodo,
            "Sigla": sigla,
            "Nombre_Programa": fila.get("programaNombre", ""),
            "Nombre_Rama": fila.get("ramaNombre", ""),
            "Nivel": nivel,
            "Modalidad": fila.get("modalidadNombre", ""),
            "Grupo_Edad": fila.get("edadNombre", ""),
            "Boleta": int(fila["boletaNombre"]) if str(fila.get("boletaNombre", "")).isdigit() else 0,
            # Corregido de "generacionNombre" a "tipoTitulacionNombre" según tu JSON
            "Tipo_Titulacion": fila.get("tipoTitulacionNombre", ""), 
        }

        # 2. Obtenemos el diccionario de turnos (si no existe, usamos uno vacío)
        turnos_dict = fila.get("turnos", {})

        # 3. Iteramos dinámicamente sobre cada turno (Matutino, Vespertino, etc.)
        for nombre_turno, generos in turnos_dict.items():
            
            # Registro para Hombres en este turno específico
            registros.append(Temp_Titulados(
                **base_comun,
                Turno=nombre_turno,
                Sexo="Hombre",
                Titulados=limpiar_numero(generos.get("hombres")),
            ))

            # Registro para Mujeres en este turno específico
            registros.append(Temp_Titulados(
                **base_comun,
                Turno=nombre_turno,
                Sexo="Mujer",
                Titulados=limpiar_numero(generos.get("mujeres")),
            ))

    return registros

def preparar_datos_temp_titulados_desde_db(
    datos: List[Dict[str, Any]],
    periodo: str,
    sigla: str,
    nivel: str,
) -> List[Temp_Titulados]:
    registros = []
    for fila in datos:
        if fila.get("Titulados") is None:
            continue  # saltar filas sin datos
        registros.append(Temp_Titulados(
            Periodo=periodo,
            Sigla=sigla,
            Nombre_Programa=fila.get("Nombre_Programa", ""),
            Nombre_Rama=fila.get("Nombre_Rama", ""),
            Nivel=nivel,
            Modalidad=fila.get("Modalidad", ""),
            Grupo_Edad=fila.get("Grupo_Edad", ""),
            Boleta=int(fila["Boleta"]) if str(fila.get("Boleta", "")).isdigit() else 0,
            Tipo_Titulacion=fila.get("Tipo_Titulacion", ""),
            Turno=fila.get("Turno", ""),
            Sexo=fila.get("Sexo", ""),
            Titulados=fila.get("Titulados"),
        ))
    return registros

#Acuse

def _nueva_tabla() -> Dict[str, int]:
    return {'H': 0, 'M': 0, 'T': 0}

def a_lista(d: dict, orden=None) -> list[dict]:
    items = sorted(d.items(), key=orden or (lambda x: str(x[0]).lower()))
    return [
        {
            'nombre': k,
            'hombres': f"{v['H']:,}",
            'mujeres': f"{v['M']:,}",
            'total': f"{v['T']:,}"
        }
        for k, v in items
    ]

def _sumar(d: dict) -> dict:
    h = sum(v['H'] for v in d.values())
    m = sum(v['M'] for v in d.values())
    return {
        'hombres': f"{h:,}",
        'mujeres': f"{m:,}",
        'total': f"{(h + m):,}"
    }


def procesar_titulados(filas: list[dict]) -> dict:
    
    programa  : Dict[str, Dict[str, int]] = defaultdict(_nueva_tabla)
    modalidad : Dict[str, Dict[str, int]] = defaultdict(_nueva_tabla)
    boleta    : Dict[str, Dict[str, int]] = defaultdict(_nueva_tabla)
    tipo_tit  : Dict[str, Dict[str, int]] = defaultdict(_nueva_tabla)
    edad      : Dict[str, Dict[str, int]] = defaultdict(_nueva_tabla)
    turno     : Dict[str, Dict[str, int]] = defaultdict(_nueva_tabla)

    for row in filas:
        sexo = row.get('Sexo', '')
        try:
            cantidad = int(row.get('Titulados', 0) or 0)
        except (ValueError, TypeError):
            cantidad = 0

        if cantidad <= 0:
            continue

        grupos = [
            (programa,  row.get('Nombre_Programa', 'Sin Programa')),
            (modalidad, row.get('Modalidad',       'Sin Modalidad')),
            (boleta,    str(row.get('Boleta',      'N/A'))),
            (tipo_tit,  row.get('Tipo_Titulacion', 'Otro')),
            (edad,      row.get('Grupo_Edad',      'N/A')),
            (turno,     row.get('Turno',           'N/A')),
        ]

        for tabla, clave in grupos:
            if sexo == 'Hombre':
                tabla[clave]['H'] += cantidad
            elif sexo == 'Mujer':
                tabla[clave]['M'] += cantidad
           
            tabla[clave]['T'] = tabla[clave]['H'] + tabla[clave]['M']

    return {
        'tabla_programas'  : a_lista(programa),
        'tabla_modalidades': a_lista(modalidad),
        'tabla_boletas'    : a_lista(boleta),
        'tabla_tipo_tit'   : a_lista(tipo_tit),
        'tabla_edades'     : a_lista(edad),
        'tabla_turnos'     : a_lista(turno),

        'totales_programas'  : _sumar(programa),
        'totales_modalidades': _sumar(modalidad),
        'totales_boletas'    : _sumar(boleta),
        'totales_tipo_tit'   : _sumar(tipo_tit),
        'totales_edades'     : _sumar(edad),
        'totales_turnos'     : _sumar(turno),

        # Total general para el encabezado
        'total_t': f"{sum(v['T'] for v in programa.values()):,}",
    }


    
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
