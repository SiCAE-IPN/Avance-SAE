from backend.services.encargado_ua_service import obtener_encargados, verificar_permiso_formato
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import false, text
from typing import List, Dict, Any
from fastapi.responses import JSONResponse
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from weasyprint import HTML, CSS
import tempfile
import os

from backend.database import db_base
from backend.database.models.Temp_Aprovechamiento import Temp_Aprovechamiento
from backend.database.connection import get_db
from backend.core.templates import templates
from backend.services.periodo_service import get_periodo_activo, get_periodo_anterior_al_ultimo, get_todos_los_periodos
from backend.services.aprovechamiento_service import get_unidades_con_niveles_asociados
from backend.database.models.CatPeriodo import CatPeriodo
from backend.database.models.CatUnidadAcademica import CatUnidadAcademica
from backend.database.models.CatNivel import CatNivel
from backend.database.models.CatSemaforo import CatSemaforo
from backend.database.models.Validacion import Validacion
from backend.database.models.SemaforoUnidadAcademica import SemaforoUnidadAcademica
from backend.database.models.SemaforoSemestreUnidadAcademica import SemaforoSemestreUnidadAcademica
from backend.database.models.CatRoles import CatRoles
from backend.database.models.Usuario import Usuario
from backend.services.nivel_service import get_niveles_by_unidad_academica
from backend.core.auth import VerificarAccesoAcuse, get_current_session
from backend.utils.request import get_request_host
from backend.services.envio_correo_service import (
    notificar_rechazo_global,
    html_correo_acuse,
    obtener_correos_involucrados,
    enviar_correo_acuse_titular,
    verificar_todos_modulos_validados_titular,
)
from datetime import datetime
from backend.core.auth import VerificarAccesoAcuse


router = APIRouter()
validar_acuse = VerificarAccesoAcuse()

# Variable global
HHost: str = "Test"


# ============================================================================
# MAPAS Y CONSTANTES
# ============================================================================

SEMESTRE_A_NUM = {
    'primer': 1, 'primero': 1,
    'segundo': 2,
    'tercer': 3, 'tercero': 3,
    'cuarto': 4,
    'quinto': 5,
    'sexto': 6,
    'séptimo': 7, 'septimo': 7,
    'octavo': 8,
    'noveno': 9,
    'décimo': 10, 'decimo': 10,
    'undécimo': 11, 'undecimo': 11, 'décimo primero': 11, 'decimo primero': 11,
    'duodécimo': 12, 'duodecimo': 12, 'décimo segundo': 12, 'decimo segundo': 12,
}

SEMAFORO_REQUERIDO = {4: 3, 5: 4, 6: 5, 7: 6, 8: 7, 9: 8}
SEMAFORO_SIGUIENTE = {4: 4, 5: 5, 6: 6, 7: 7, 8: 8, 9: 9}
SEMAFORO_RECHAZO   = {4: 10, 5: 11, 6: 12, 7: 13, 8: 14, 9: 15}
ID_FORMATO_APROVECHAMIENTO = 2

# ============================================================================
# FUNCIONES AUXILIARES DE TRANSFORMACIÓN
# ============================================================================

def semestre_texto_a_numero(texto):
    if texto is None:
        return None
    t = str(texto).strip().lower()
    if t in SEMESTRE_A_NUM:
        return SEMESTRE_A_NUM[t]
    try:
        return int(t)
    except ValueError:
        return None

def normalizar_sexo(sexo):
    s = str(sexo).strip().upper()
    if s in ('H', 'HOMBRE', 'MASCULINO'):
        return 'Hombre'
    if s in ('M', 'MUJER', 'FEMENINO'):
        return 'Mujer'
    return 'Otro'

MAPA_APROVECHAMIENTO_CORTO = {
    'aprobados': 'A',
    'baja temporal': 'B. T.',
    'baja definitiva': 'B. D.',
    'deserción': 'D',
    'desercion': 'D',
    'r': 'R',
    'reincorporados': 'R',
    'reincorporado': 'R',
    'reincorporadas': 'R',
    'reincorporada': 'R',
    'reincorporación': 'R',
    'reincorporacion': 'R',
    'reprobada 1 materia': 'R1',
    'reprobadas 1 materia': 'R1',
    'reprobadas 1': 'R1',
    'reprobada 1': 'R1',
    'reprobada 2 materias': 'R2',
    'reprobadas 2 materias': 'R2',
    'reprobadas 2': 'R2',
    'reprobada 2': 'R2',
    'reprobada 3 materias': 'R3',
    'reprobadas 3 materias': 'R3',
    'reprobadas 3': 'R3',
    'reprobada 3': 'R3',
    'reprobada 4 materias': 'R4',
    'reprobadas 4 materias': 'R4',
    'reprobadas 4': 'R4',
    'reprobada 4': 'R4',
    'reprobada 5 materias': 'R5',
    'reprobadas 5 materias': 'R5',
    'reprobadas 5': 'R5',
    'reprobada 5': 'R5',
    'reprobada 6 o más': 'R6',
    'reprobadas 6 o más': 'R6',
    'reprobadas 6 o mas': 'R6',
    'reprobada 6 o mas': 'R6',
    'reprobadas 6': 'R6',
    'reprobada 6': 'R6',
}

LEYENDA_APROVECHAMIENTO_MAP = {
    'A': 'Aprobados',
    'B. T.': 'Baja Temporal',
    'B. D.': 'Baja Definitiva',
    'D': 'Deserción',
    'R': 'Reincorporados',
    'R1': 'Reprobada 1 materia',
    'R2': 'Reprobadas 2 materias',
    'R3': 'Reprobadas 3 materias',
    'R4': 'Reprobadas 4 materias',
    'R5': 'Reprobadas 5 materias',
    'R6': 'Reprobadas 6 o más materias',
}

def normalizar_tipo_aprovechamiento(apr_raw):
    k = str(apr_raw or '').strip().lower()
    return MAPA_APROVECHAMIENTO_CORTO.get(k, str(apr_raw or '').strip())

def obtener_columnas_aprovechamiento_acotadas(rows):
    tipos_en_datos = set()
    for r in rows:
        apr = r.get("Aprovechamiento")
        if apr:
            tipos_en_datos.add(normalizar_tipo_aprovechamiento(apr))
    
    orden_preferido = ['A', 'B. T.', 'B. D.', 'D', 'R', 'R1', 'R2', 'R3', 'R4', 'R5', 'R6']
    columnas = []
    for t in orden_preferido:
        if t in tipos_en_datos or not tipos_en_datos:
            columnas.append(t)
    for t in sorted(tipos_en_datos):
        if t not in columnas:
            columnas.append(t)
    if not columnas:
        columnas = ['A', 'B. T.', 'B. D.', 'D', 'R', 'R1', 'R2', 'R3', 'R4', 'R5', 'R6']
    return columnas

def obtener_tipos_aprovechamiento(rows):
    tipos = set()
    for r in rows:
        apr = r.get("Aprovechamiento")
        if apr:
            tipos.add(str(apr).strip())
    orden_base = ['Aprobados', 'Deserción', 'Baja Definitiva', 'Baja Temporal']
    otros = sorted([t for t in tipos if t not in orden_base and not es_reincorporado(t)])
    return orden_base + otros

def es_reincorporado(apr_raw):
    k = str(apr_raw or '').strip().lower()
    return normalizar_tipo_aprovechamiento(apr_raw) == 'R' or 'reinc' in k or k == 'r'

def deduplicar_rows_aprovechamiento(rows):
    """
    Deduplica filas devueltas por SP_Consulta_Aprovechamiento_Unidad_Academica.
    Evita sumas dobles o triples causadas por joins con Semaforo_Semestre_Unidad_Academica
    o uniones en el SP que retornan la misma fila con diferente Id_Semaforo.
    """
    vistos = set()
    unicos = []
    for r in rows:
        prog = str(r.get("Nombre_Programa") or "").strip().lower()
        modalidad = str(r.get("Modalidad") or "").strip().lower()
        turno = str(r.get("Turno") or "").strip().lower()
        semestre = str(r.get("Semestre") or "").strip().lower()
        apr = normalizar_tipo_aprovechamiento(r.get("Aprovechamiento"))
        sexo = normalizar_sexo(r.get("Sexo"))
        alumnos = int(r.get("alumnos") or r.get("Alumnos") or 0)

        clave = (prog, modalidad, turno, semestre, apr, sexo, alumnos)
        if clave not in vistos:
            vistos.add(clave)
            unicos.append(r)
    return unicos

def deduplicar_rows_inscritos(rows):
    """Deduplica filas de inscritos para evitar conteos repetidos."""
    vistos = set()
    unicos = []
    for r in rows:
        prog = str(r.get("Nombre_Programa") or "").strip().lower()
        semestre = str(r.get("Semestre") or "").strip().lower()
        modalidad = str(r.get("Modalidad") or "").strip().lower()
        turno = str(r.get("Turno") or "").strip().lower()
        sexo = normalizar_sexo(r.get("Sexo"))
        matricula = int(r.get("alumnos") or r.get("Alumnos") or r.get("Matricula") or r.get("matricula") or 0)

        clave = (prog, semestre, modalidad, turno, sexo, matricula)
        if clave not in vistos:
            vistos.add(clave)
            unicos.append(r)
    return unicos

def sumar_hm(rows, clave_cantidad=None):
    """Suma alumnos por sexo. Devuelve {'h','m','t'}."""
    h = m = 0
    for r in rows:
        cant = int(r.get("alumnos") or r.get("Alumnos") or r.get("Matricula") or r.get("matricula") or 0)
        sexo = normalizar_sexo(r.get("Sexo", r.get("sexo", "")))
        if sexo == 'Hombre':
            h += cant
        elif sexo == 'Mujer':
            m += cant
    return {"h": h, "m": m, "t": h + m}

# ============================================================================
# FUNCIONES DE PROCESAMIENTO DE TABLAS (TRANSPUESTAS)
# ============================================================================

def procesar_tabla_programa(rows):
    columnas_tipos = obtener_columnas_aprovechamiento_acotadas(rows)
    programas = sorted({r.get("Nombre_Programa", "").strip() for r in rows if r.get("Nombre_Programa")})
    
    suma = defaultdict(int)
    for r in rows:
        prog = r.get("Nombre_Programa", "").strip()
        if not prog:
            continue
        apr = normalizar_tipo_aprovechamiento(r.get("Aprovechamiento", ""))
        sexo = normalizar_sexo(r.get("Sexo", ""))
        alumnos = int(r.get("alumnos") or 0)
        suma[(prog, apr, sexo)] += alumnos

    filas = []
    for prog in programas:
        hombres = [suma.get((prog, apr, 'Hombre'), 0) for apr in columnas_tipos]
        mujeres = [suma.get((prog, apr, 'Mujer'), 0) for apr in columnas_tipos]
        subtotales = [h + m for h, m in zip(hombres, mujeres)]
        filas.append({
            "nombre": prog,
            "hombres": hombres,
            "total_h": sum(hombres),
            "mujeres": mujeres,
            "total_m": sum(mujeres),
            "subtotales": subtotales,
            "total_st": sum(subtotales),
        })

    totales_h_col = [sum(f["hombres"][idx] for f in filas) for idx in range(len(columnas_tipos))]
    totales_m_col = [sum(f["mujeres"][idx] for f in filas) for idx in range(len(columnas_tipos))]
    totales_general_col = [h + m for h, m in zip(totales_h_col, totales_m_col)]

    total_gen_h = sum(totales_h_col)
    total_gen_m = sum(totales_m_col)
    total_gen_absoluto = total_gen_h + total_gen_m

    leyenda = [{"sigla": col, "significado": LEYENDA_APROVECHAMIENTO_MAP.get(col, col)} for col in columnas_tipos]

    return {
        "columnas": columnas_tipos,
        "filas": filas,
        "totales_h_col": totales_h_col,
        "total_gen_h": total_gen_h,
        "totales_m_col": totales_m_col,
        "total_gen_m": total_gen_m,
        "totales_general_col": totales_general_col,
        "total_general_t": total_gen_absoluto,
        "leyenda": leyenda,
    }

def procesar_tabla_semestre(rows):
    columnas_tipos = obtener_columnas_aprovechamiento_acotadas(rows)
    semestres_numeros = set()
    for r in rows:
        sem_num = semestre_texto_a_numero(r.get("Semestre"))
        if sem_num is not None and isinstance(sem_num, int):
            semestres_numeros.add(sem_num)
    semestres_ordenados = sorted(semestres_numeros)
    if not semestres_ordenados:
        semestres_ordenados = [1, 2, 3, 4, 5, 6]

    suma = defaultdict(int)
    for r in rows:
        sem_num = semestre_texto_a_numero(r.get("Semestre"))
        if sem_num is None:
            continue
        apr = normalizar_tipo_aprovechamiento(r.get("Aprovechamiento", ""))
        sexo = normalizar_sexo(r.get("Sexo", ""))
        alumnos = int(r.get("alumnos") or 0)
        suma[(sem_num, apr, sexo)] += alumnos

    filas = []
    for sem in semestres_ordenados:
        hombres = [suma.get((sem, apr, 'Hombre'), 0) for apr in columnas_tipos]
        mujeres = [suma.get((sem, apr, 'Mujer'), 0) for apr in columnas_tipos]
        subtotales = [h + m for h, m in zip(hombres, mujeres)]
        filas.append({
            "nombre": f"Semestre {sem}",
            "hombres": hombres,
            "total_h": sum(hombres),
            "mujeres": mujeres,
            "total_m": sum(mujeres),
            "subtotales": subtotales,
            "total_st": sum(subtotales),
        })

    totales_h_col = [sum(f["hombres"][idx] for f in filas) for idx in range(len(columnas_tipos))]
    totales_m_col = [sum(f["mujeres"][idx] for f in filas) for idx in range(len(columnas_tipos))]
    totales_general_col = [h + m for h, m in zip(totales_h_col, totales_m_col)]

    total_gen_h = sum(totales_h_col)
    total_gen_m = sum(totales_m_col)
    total_gen_absoluto = total_gen_h + total_gen_m

    leyenda = [{"sigla": col, "significado": LEYENDA_APROVECHAMIENTO_MAP.get(col, col)} for col in columnas_tipos]

    return {
        "columnas": columnas_tipos,
        "filas": filas,
        "totales_h_col": totales_h_col,
        "total_gen_h": total_gen_h,
        "totales_m_col": totales_m_col,
        "total_gen_m": total_gen_m,
        "totales_general_col": totales_general_col,
        "total_general_t": total_gen_absoluto,
        "leyenda": leyenda,
    }

def procesar_tabla_modalidad(rows):
    tipos_aprov = obtener_tipos_aprovechamiento(rows)
    modalidades = sorted({r.get("Modalidad", "").strip() for r in rows if r.get("Modalidad")})
    categorias = modalidades
    suma = defaultdict(int)
    for r in rows:
        mod = r.get("Modalidad", "").strip()
        if not mod:
            continue
        apr = r.get("Aprovechamiento", "").strip()
        sexo = normalizar_sexo(r.get("Sexo", ""))
        alumnos = int(r.get("alumnos") or 0)
        suma[(mod, apr, sexo)] += alumnos

    filas = []
    for apr in tipos_aprov:
        celdas = []
        total_h_tipo = 0
        total_m_tipo = 0
        for mod in modalidades:
            h = suma.get((mod, apr, 'Hombre'), 0)
            m = suma.get((mod, apr, 'Mujer'), 0)
            t = h + m
            celdas.append({"h": h, "m": m, "t": t})
            total_h_tipo += h
            total_m_tipo += m
        filas.append({
            "tipo": apr,
            "celdas": celdas,
            "total_h": total_h_tipo,
            "total_m": total_m_tipo,
            "total_t": total_h_tipo + total_m_tipo,
        })

    totales_por_columna = []
    for idx_mod, mod in enumerate(modalidades):
        h = sum(filas[idx_tipo]["celdas"][idx_mod]["h"] for idx_tipo in range(len(tipos_aprov)))
        m = sum(filas[idx_tipo]["celdas"][idx_mod]["m"] for idx_tipo in range(len(tipos_aprov)))
        totales_por_columna.append({"h": h, "m": m, "t": h + m})

    total_general_h = sum(fila["total_h"] for fila in filas)
    total_general_m = sum(fila["total_m"] for fila in filas)

    return {
        "categorias": categorias,
        "filas": filas,
        "totales_por_columna": totales_por_columna,
        "total_general_h": total_general_h,
        "total_general_m": total_general_m,
        "total_general_t": total_general_h + total_general_m,
    }

def procesar_tabla_turno(rows):
    tipos_aprov = obtener_tipos_aprovechamiento(rows)
    turnos = sorted({r.get("Turno", "").strip() for r in rows if r.get("Turno")})
    categorias = turnos
    suma = defaultdict(int)
    for r in rows:
        tur = r.get("Turno", "").strip()
        if not tur:
            continue
        apr = r.get("Aprovechamiento", "").strip()
        sexo = normalizar_sexo(r.get("Sexo", ""))
        alumnos = int(r.get("alumnos") or 0)
        suma[(tur, apr, sexo)] += alumnos

    filas = []
    for apr in tipos_aprov:
        celdas = []
        total_h_tipo = 0
        total_m_tipo = 0
        for tur in turnos:
            h = suma.get((tur, apr, 'Hombre'), 0)
            m = suma.get((tur, apr, 'Mujer'), 0)
            t = h + m
            celdas.append({"h": h, "m": m, "t": t})
            total_h_tipo += h
            total_m_tipo += m
        filas.append({
            "tipo": apr,
            "celdas": celdas,
            "total_h": total_h_tipo,
            "total_m": total_m_tipo,
            "total_t": total_h_tipo + total_m_tipo,
        })

    totales_por_columna = []
    for idx_tur, tur in enumerate(turnos):
        h = sum(filas[idx_tipo]["celdas"][idx_tur]["h"] for idx_tipo in range(len(tipos_aprov)))
        m = sum(filas[idx_tipo]["celdas"][idx_tur]["m"] for idx_tipo in range(len(tipos_aprov)))
        totales_por_columna.append({"h": h, "m": m, "t": h + m})

    total_general_h = sum(fila["total_h"] for fila in filas)
    total_general_m = sum(fila["total_m"] for fila in filas)

    return {
        "categorias": categorias,
        "filas": filas,
        "totales_por_columna": totales_por_columna,
        "total_general_h": total_general_h,
        "total_general_m": total_general_m,
        "total_general_t": total_general_h + total_general_m,
    }

# ============================================================================
# FUNCIÓN COMPARTIDA PARA OBTENER EL CONTEXTO (HTML y PDF)
# ============================================================================

async def obtener_contexto_aprovechamiento(
    request: Request,
    periodo: str,
    nivel: str,
    unidad: str,
    sess,
    db: Session,
    exportando_pdf: bool = False,
    no_validado: bool = False
):
    id_rol = int(getattr(sess, 'id_rol', 0) or 0)
    nombre_rol = getattr(sess, 'nombre_rol', '') or ''
    nombre_usuario = getattr(sess, 'nombre_usuario', '') or ''
    apellidoP_usuario = getattr(sess, 'apellidoP_usuario', '') or ''
    apellidoM_usuario = getattr(sess, 'apellidoM_usuario', '') or ''
    nombre_completo = " ".join(filter(None, [nombre_usuario, apellidoP_usuario, apellidoM_usuario]))
    id_usuario_actual = int(getattr(sess, 'id_usuario', 0) or 0)
    if not unidad:
        unidad = (getattr(sess, 'sigla_unidad_academica', '') or '').strip()
    usuario_login = nombre_usuario or "sistema"
    host = request.client.host

    tabla_programas = None
    tabla_semestres = None
    tabla_modalidades = None
    tabla_turnos = None
    error = None
    resumen_inscritos = {"h": 0, "m": 0, "t": 0}
    resumen_reincorporados = {"h": 0, "m": 0, "t": 0}
    nombre_ua = unidad or "—"
    periodo_activo = False
    puede_validar = False
    usuario_ya_valido = False
    usuario_ya_rechazo = False
    periodo_anterior_literal = None
    nombre_capturista = "No asignado"
    nombre_ceget = "No asignado"
    nombre_titular = "No asignado"

    try:
        periodo_obj = db.query(CatPeriodo).filter(CatPeriodo.Periodo == periodo).first()
        periodo_activo = periodo_obj is not None and periodo_obj.Id_Estatus == 1

        Periodoant = get_periodo_anterior_al_ultimo(db)
        Id_Periodo_anterior = Periodoant[0] if Periodoant else None
        periodo_anterior_literal = Periodoant[1] if Periodoant else None

        nivel_obj = db.query(CatNivel).filter(CatNivel.Nivel == nivel).first()
        Id_Nivel = nivel_obj.Id_Nivel if nivel_obj else None

        ua_obj = db.query(CatUnidadAcademica).filter(CatUnidadAcademica.Sigla == unidad).first()
        Id_Unidad_Academica = ua_obj.Id_Unidad_Academica if ua_obj else None

        # ===================================
        # REPOSITORIO DE NOMBRES PARA FIRMAS
        # ===================================
        if Id_Unidad_Academica:
            encargados = obtener_encargados(db, Id_Unidad_Academica, 2, Id_Nivel)
            nombre_capturista = encargados["nombre_capturista"]
            nombre_ceget      = encargados["nombre_ceget"]
            nombre_titular    = encargados["nombre_titular"]
            print(f"Capturista: {nombre_capturista}, CEGET: {nombre_ceget}, Titular: {nombre_titular}")

        estado_semaforo_actual = 0
        esperando_por_rol = "Capturista"
        pendiente_validacion = False

        if Id_Periodo_anterior and Id_Unidad_Academica and Id_Nivel:
            semaforo_actual = db.query(SemaforoUnidadAcademica).filter(
                SemaforoUnidadAcademica.Id_Periodo == Id_Periodo_anterior,
                SemaforoUnidadAcademica.Id_Unidad_Academica == Id_Unidad_Academica,
                SemaforoUnidadAcademica.Id_Formato == ID_FORMATO_APROVECHAMIENTO,
                SemaforoUnidadAcademica.Id_Nivel == Id_Nivel
            ).first()
            if semaforo_actual:
                estado_semaforo = semaforo_actual.Id_Semaforo
                estado_semaforo_actual = estado_semaforo
                
                # Calcular puede_validar / usuario_ya_valido solo si id_rol está en SEMAFORO_REQUERIDO y periodo_activo es True
                if not exportando_pdf and id_rol in SEMAFORO_REQUERIDO:
                    semaforo_requerido = SEMAFORO_REQUERIDO.get(id_rol)
                    if estado_semaforo == semaforo_requerido and periodo_activo:
                        puede_validar = True
                    elif estado_semaforo >= id_rol:
                        usuario_ya_valido = True
                
                # ==== CALCULAR QUIÉN SIGUE ====
                semaforo_a_siguiente_rol = {
                    3: 4,  # Semáforo 3 -> Sigue CEGET (4)
                    4: 5,  # Semáforo 4 -> Sigue Titular (5)
                    5: 6,  # Semáforo 5 -> Sigue Analista (6)
                    6: 7,  # Semáforo 6 -> Sigue Jefe Depto (7)
                    7: 8,  # Semáforo 7 -> Sigue Jefe División (8)
                    8: 9,  # Semáforo 8 -> Sigue Director (9)
                }
                
                # Obtenemos el ID del rol que sigue (si es menor a 3, sigue siendo Capturista)
                siguiente_rol_id = semaforo_a_siguiente_rol.get(estado_semaforo_actual, 3)
                
                # Consultamos el nombre real del rol en la base de datos
                rol_obj = db.query(CatRoles).filter(CatRoles.Id_Rol == siguiente_rol_id).first()
                if rol_obj:
                    esperando_por_rol = rol_obj.Rol

            if not exportando_pdf and id_rol in SEMAFORO_REQUERIDO and id_usuario_actual and Id_Periodo_anterior:
                validacion_rechazo = db.query(Validacion).filter(
                    Validacion.Id_Periodo == Id_Periodo_anterior,
                    Validacion.Id_Usuario == id_usuario_actual,
                    Validacion.Id_Formato == ID_FORMATO_APROVECHAMIENTO,
                    Validacion.Validado == 0
                ).first()
                if validacion_rechazo and not puede_validar:
                    usuario_ya_rechazo = True
                    puede_validar = False

            # Si existe un estado previo pero ya no hay rechazo vigente ni es turno de validar,
            # mostramos el estado como pendiente en lugar de "rechazado".
            if not puede_validar and not usuario_ya_valido and not usuario_ya_rechazo and estado_semaforo_actual > 0:
                pendiente_validacion = True

        connection = db.connection()
        resultado = connection.execute(
            text("""
                SET NOCOUNT ON;
                EXEC [dbo].[SP_Consulta_Aprovechamiento_Unidad_Academica]
                    @UUnidad_Academica = :unidad,
                    @Pperiodo          = :periodo,
                    @NNivel            = :nivel,
                    @UUsuario          = :usuario,
                    @HHost             = :host
            """),
            {"unidad": unidad, "periodo": periodo, "nivel": nivel, "usuario": usuario_login, "host": host}
        )
        columnas = list(resultado.keys()) if resultado.returns_rows else []
        rows_raw = [dict(zip(columnas, row)) for row in resultado.fetchall()] if resultado.returns_rows else []

        nota_rechazo = None
        try:
            for r in rows_raw:
                if "Nota" in r and r["Nota"] and str(r["Nota"]).strip().lower() not in ('none', 'null', ''):
                    nota_rechazo = str(r["Nota"]).strip()
                    break
            if not nota_rechazo and hasattr(resultado, 'cursor') and hasattr(resultado.cursor, 'nextset'):
                while resultado.cursor.nextset():
                    n_rows = resultado.cursor.fetchall()
                    if n_rows and len(n_rows) > 0:
                        p_row = n_rows[0]
                        val = p_row[0] if isinstance(p_row, (list, tuple)) else getattr(p_row, 'Nota', str(p_row))
                        if val and str(val).strip().lower() not in ('none', 'null', ''):
                            nota_rechazo = str(val).strip()
                            break
        except Exception as e_nextset:
            print(f"⚠️ Error al capturar nota de rechazo en obtener_contexto_aprovechamiento: {e_nextset}")

        if not rows_raw:
            error = "No se encontraron datos para los filtros seleccionados."
        else:
            # Deduplicamos filas de aprovechamiento para prevenir sumas dobles por joins de semáforo
            rows_raw = deduplicar_rows_aprovechamiento(rows_raw)

            # Los Reincorporados ya no van en las tablas: se muestran en la tabla resumen al inicio del acuse.
            rows_tablas = [r for r in rows_raw if not es_reincorporado(r.get("Aprovechamiento"))]
            resumen_reincorporados = sumar_hm([r for r in rows_raw if es_reincorporado(r.get("Aprovechamiento"))])
            try:
                res_insc = db.execute(text("""
                    SET NOCOUNT ON;
                    EXEC dbo.SP_Consulta_Inscritos_Aprovechamiento
                        @PPeriodo = :PPeriodo,
                        @SSigla_Unidad_Academica = :UUnidad_Academica,
                        @NNivel = :NNivel;
                """), {"PPeriodo": periodo, "UUnidad_Academica": unidad, "NNivel": nivel})
                rows_insc = [dict(r) for r in res_insc.mappings().all()] if res_insc.returns_rows else []
                rows_insc = deduplicar_rows_inscritos(rows_insc)
                resumen_inscritos = sumar_hm(rows_insc)
            except Exception as e_insc:
                print(f"⚠️ No se pudo obtener Inscritos para el acuse: {e_insc}")
                resumen_inscritos = {"h": 0, "m": 0, "t": 0}

            # Totales calculados para la tabla unificada (filas y columnas)
            resumen_totales = {
                "h": resumen_inscritos["h"] + resumen_reincorporados["h"],
                "m": resumen_inscritos["m"] + resumen_reincorporados["m"],
                "t": resumen_inscritos["t"] + resumen_reincorporados["t"]
            }

            tabla_programas  = procesar_tabla_programa(rows_tablas)
            tabla_semestres  = procesar_tabla_semestre(rows_tablas)
            tabla_modalidades = procesar_tabla_modalidad(rows_tablas)
            tabla_turnos     = procesar_tabla_turno(rows_tablas)

    except Exception as e:
        import traceback
        error = f"Error al generar resumen de aprovechamiento: {e}"
        print(traceback.format_exc())

    return {
        "request": request,
        "session": sess,
        "periodo": periodo_anterior_literal or periodo,
        "periodo_url": periodo,
        "nivel": nivel,
        "unidad": unidad,
        "nombre_ua": nombre_ua,
        "nombre_completo": nombre_completo,
        "nombre_rol": nombre_rol,
        "id_rol": id_rol,
        "tabla_programa": tabla_programas,
        "tabla_semestre": tabla_semestres,
        "tabla_modalidad": tabla_modalidades,
        "tabla_turno": tabla_turnos,
        "resumen_inscritos": resumen_inscritos,
        "resumen_reincorporados": resumen_reincorporados,
        "resumen_totales": resumen_totales,
        "periodo_activo": periodo_activo,
        "puede_validar": puede_validar,
        "usuario_ya_valido": usuario_ya_valido,
        "usuario_ya_rechazo": usuario_ya_rechazo,
        "error": error,
        "exportando_pdf": exportando_pdf,
        "fecha_hoy": datetime.now().strftime("%d/%m/%Y"),
        "estado_semaforo_actual": estado_semaforo_actual,
        "esperando_por_rol": esperando_por_rol,
        "pendiente_validacion": pendiente_validacion,
        "nota_rechazo": nota_rechazo,
        "nombre_capturista": nombre_capturista,
        "nombre_ceget": nombre_ceget,
        "nombre_titular": nombre_titular,
    }

# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/consulta", response_class=HTMLResponse)
def aprovechamiento_view(request: Request, sess=Depends(validar_acuse), db: Session = Depends(get_db)):
    Rol = str(getattr(sess, 'nombre_rol', '') or '')
    UUsuario = getattr(sess, 'usuario', '') or ''
    UUnidad_Academica = str(getattr(sess, 'sigla_unidad_academica', '') or '')
    NNivel = str(getattr(sess, 'nombre_nivel', '') or '')
    HHost = request.client.host

    periodo_literal = get_periodo_activo(db)
    PPeriodo = periodo_literal[1]
    ID_PPeriodo = periodo_literal[0]
    periodo_anterior_id, periodo_anterior_literal = get_periodo_anterior_al_ultimo(db)
    periodo_aprovechamiento = periodo_anterior_literal or PPeriodo
    Id_Unidad_Academica = int(getattr(sess, 'id_unidad_academica', 0) or 0)
    nombre_completo = getattr(sess, 'nombre_completo', '')

    id_rol = int(getattr(sess, 'id_rol', 0) or 0)
    roles_permitidos = [1, 3, 4, 5, 6, 7, 8, 9]
    if id_rol not in roles_permitidos:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_message": "Acceso denegado: Su rol no tiene permisos para acceder a esta funcionalidad.",
            "redirect_url": "/mod_principal/",
            "session": sess
        })

    if Rol == "Capturista" or id_rol == 3:
        aprovechamientos_limpios = []
        reincorporados_detallados = []
        inscritos_final = []
        rama = ""
        id_nivel = int(sess.id_nivel)
        rechazo_info = None
        matricula_rechazada = False
        usuario_ya_valido = False
        usuario_ya_rechazo = False
        id_usuario= int(getattr(sess, 'id_usuario', 0) or 0)
        
        try:
            verificar_permiso_formato(db, id_usuario, 2)
        except HTTPException as e:
            return templates.TemplateResponse("error.html", {
            "request": request,
            "error_message": e.detail,
            "redirect_url": "/mod_principal/",
            "session": sess
            })

        
        try:
            # ---- Obtener datos del SP de aprovechamiento ----
            connection = db.connection()
            query_aprov = text("""
                SET NOCOUNT ON;
                EXEC dbo.SP_Consulta_Aprovechamiento_Unidad_Academica
                    @UUnidad_Academica = :UUnidad_Academica, 
                    @PPeriodo = :PPeriodo,
                    @NNivel = :NNivel, 
                    @UUsuario = :UUsuario, 
                    @HHost = :HHost;
            """)
            result_aprov = connection.execute(query_aprov, {
                "UUnidad_Academica": UUnidad_Academica,
                "PPeriodo": PPeriodo,
                "NNivel": NNivel,
                "UUsuario": UUsuario,
                "HHost": HHost
            })
            
            rows_aprov = result_aprov.fetchall() if result_aprov.returns_rows else []
            cols_aprov = list(result_aprov.keys()) if result_aprov.returns_rows else []
            aprovechamientos_raw = [dict(zip(cols_aprov, row)) for row in rows_aprov]

            # Capturar nota de rechazo del SP (segundo result set o columna en datos)
            nota_rechazo_sp = None
            try:
                for r in aprovechamientos_raw:
                    if "Nota" in r and r["Nota"] and str(r["Nota"]).strip().lower() not in ('none', 'null', ''):
                        nota_rechazo_sp = str(r["Nota"]).strip()
                        break
                if not nota_rechazo_sp and hasattr(result_aprov, 'cursor') and hasattr(result_aprov.cursor, 'nextset'):
                    while result_aprov.cursor.nextset():
                        nota_rows = result_aprov.cursor.fetchall()
                        if nota_rows and len(nota_rows) > 0:
                            p_row = nota_rows[0]
                            if isinstance(p_row, (list, tuple)) and len(p_row) > 0:
                                val = p_row[0]
                            elif isinstance(p_row, dict):
                                val = p_row.get("Nota") or next(iter(p_row.values()), None)
                            else:
                                val = getattr(p_row, "Nota", None) or str(p_row)
                            if val and str(val).strip().lower() not in ('none', 'null', ''):
                                nota_rechazo_sp = str(val).strip()
                                print(f"📋 Nota de rechazo capturada del SP de Aprovechamiento: {nota_rechazo_sp}")
                                break
            except Exception as e_nextset:
                print(f"⚠️ Error al obtener segundo resultset (nota rechazo) de Aprovechamiento: {e_nextset}")

            query_inscritos = text("""
                SET NOCOUNT ON;
                EXEC dbo.SP_Consulta_Inscritos_Aprovechamiento
                    @PPeriodo = :PPeriodo,
                    @SSigla_Unidad_Academica = :UUnidad_Academica,
                    @NNivel = :NNivel;
            """)
            result_inscritos = db.execute(query_inscritos, {
                "PPeriodo": PPeriodo,
                "UUnidad_Academica": UUnidad_Academica,
                "NNivel": NNivel
            })
            if result_inscritos.returns_rows:
                inscritos_final = [dict(row) for row in result_inscritos.mappings().all()]
            else:
                inscritos_final = []

            # ---- LÓGICA DE RECHAZO ----
            print(f"🔑 Parámetros para rechazo:")
            print(f"   periodo_anterior_id = {periodo_anterior_id}")
            print(f"   Id_Unidad_Academica = {Id_Unidad_Academica}")
            print(f"   id_nivel (entero) = {id_nivel}")
            print(f"   Id_Formato = 2 (Aprovechamiento)")
            print(f"   nota_rechazo_sp = {nota_rechazo_sp}")

            from backend.services.notificacion import notificacion_rechazo
            info_rechazo_db = notificacion_rechazo(
                db=db,
                periodo_anterior_id=periodo_anterior_id,
                Id_Unidad_Academica=Id_Unidad_Academica,
                id_formato=2,
                id_nivel=id_nivel
            )
            if not info_rechazo_db:
                info_rechazo_db = notificacion_rechazo(
                    db=db,
                    periodo_anterior_id=periodo_anterior_id,
                    Id_Unidad_Academica=Id_Unidad_Academica,
                    id_formato=2
                )

            rechazo_info = info_rechazo_db.copy() if info_rechazo_db else None

            # Si el SP trajo nota de rechazo, tiene prioridad
            if nota_rechazo_sp:
                if rechazo_info:
                    rechazo_info['motivo'] = nota_rechazo_sp
                else:
                    rechazo_info = {
                        'motivo': nota_rechazo_sp,
                        'rechazado_por': 'Validador',
                        'fecha': ''
                    }

            # Verificar si el capturista ya completó la captura (semáforo >= 3)
            semaforo_captura = db.query(SemaforoUnidadAcademica).filter(
                SemaforoUnidadAcademica.Id_Periodo == periodo_anterior_id,
                SemaforoUnidadAcademica.Id_Unidad_Academica == Id_Unidad_Academica,
                SemaforoUnidadAcademica.Id_Formato == 2,
                SemaforoUnidadAcademica.Id_Nivel == id_nivel
            ).first()
            estado_captura = int(semaforo_captura.Id_Semaforo or 0) if semaforo_captura else 0
            capturista_captura_completa = estado_captura >= 3

            # Si la captura está completa, ocultar cualquier rechazo histórico
            if capturista_captura_completa:
                rechazo_info = None
                usuario_ya_valido = True   # Bloquear acciones
                usuario_ya_rechazo = False

            # Determinar matricula_rechazada (para validación masiva)
            matricula_rechazada = (not capturista_captura_completa) and (rechazo_info is not None)

            # ---- Procesamiento de datos de aprovechamiento (existente) ----
            if aprovechamientos_raw:
                todos_en_tres = all(str(reg.get("Id_Semaforo")) == "3" for reg in aprovechamientos_raw)
                print("Todos en tres:",todos_en_tres)
                if todos_en_tres:
                    Periodoant = get_periodo_anterior_al_ultimo(db)
                    Id_Periodo_anterior = Periodoant[0]
                    semaforoUA = db.query(SemaforoUnidadAcademica).filter(
                        SemaforoUnidadAcademica.Id_Periodo == Id_Periodo_anterior,
                        SemaforoUnidadAcademica.Id_Unidad_Academica == Id_Unidad_Academica,
                        SemaforoUnidadAcademica.Id_Formato == 2,
                        SemaforoUnidadAcademica.Id_Nivel == id_nivel
                    ).first()
                    db.commit()
                    if semaforoUA and semaforoUA.Id_Semaforo == 2:
                        query_finaliza = text("""
                            SET NOCOUNT ON;
                            EXEC [dbo].[SP_Finaliza_Captura_Aprovechamiento] 
                                @PPeriodo = :PPeriodo,
                                @UUnidad_Academica = :UUnidad_Academica,
                                @MModalidad = :MModalidad,
                                @PPrograma = :PPrograma,
                                @SSemestre = :SSemestre,
                                @UUsuario = :UUsuario,
                                @HHost = :HHost,
                                @NNivel = :NNivel;
                        """)
                        combinaciones_procesadas = set()
                        for reg in aprovechamientos_raw:
                            m_modalidad = reg.get("Modalidad", "")
                            p_programa = reg.get("Nombre_Programa", "")
                            s_semestre = reg.get("Semestre", "")
                            combinacion_actual = (m_modalidad, p_programa, s_semestre)
                            if combinacion_actual not in combinaciones_procesadas:
                                combinaciones_procesadas.add(combinacion_actual)
                                db.execute(query_finaliza, {
                                    "PPeriodo": PPeriodo,
                                    "UUnidad_Academica": UUnidad_Academica,
                                    "MModalidad": m_modalidad,
                                    "PPrograma": p_programa,
                                    "SSemestre": s_semestre,
                                    "UUsuario": UUsuario,
                                    "HHost": HHost,
                                    "NNivel": NNivel
                                })
                        try:
                            db.commit()
                            db.refresh(semaforoUA)
                        except Exception as e:
                            db.rollback()
                            print(f"Error al guardar los cambios en BD: {e}")

                rama = aprovechamientos_raw[0].get("Nombre_Rama", "")
                periodo_aprovechamiento = aprovechamientos_raw[0].get("Periodo")
                for reg in aprovechamientos_raw:
                    reg.pop("Periodo", None)
                    situacion = str(reg.get("Aprovechamiento", "")).strip().lower()
                    if situacion == "reincorporados":
                        reincorporados_detallados.append(reg)
                    else:
                        aprovechamientos_limpios.append(reg)
        except Exception as e:
            print(f"--- ERROR DETECTADO ---\nMensaje: {e}")


        print(f"📢 [DEBUG] rechazo_info = {rechazo_info}")
        print(f"📢 [DEBUG] matricula_rechazada = {matricula_rechazada}")
        return templates.TemplateResponse(
            "aprovechamiento_consulta.html",
            {
                "rol": Rol,
                "nombre_usuario": nombre_completo,
                "periodo": periodo_aprovechamiento,
                "unidad_academica": UUnidad_Academica,
                "request": request,
                "session": sess,
                "aprovechamientos": aprovechamientos_limpios,
                "inscritos": inscritos_final,
                "reincorporados": reincorporados_detallados,
                "rama": rama,
                # Nuevas variables para el manejo de rechazo en la plantilla
                "rechazo_info": rechazo_info,
                "matricula_rechazada": matricula_rechazada,
                "usuario_ya_valido": usuario_ya_valido,
                "usuario_ya_rechazo": usuario_ya_rechazo,
            }
        )
    
    

    elif Rol == "CEGET" or Rol == "Titular":
        niveles = get_niveles_by_unidad_academica(db, Id_Unidad_Academica)
        niveles.sort(key=lambda x: x.Id_Nivel)
        id_nivel = int(sess.id_nivel)
        semaforo_captura = db.query(SemaforoUnidadAcademica).filter(
                SemaforoUnidadAcademica.Id_Periodo == periodo_anterior_id,
                SemaforoUnidadAcademica.Id_Unidad_Academica == Id_Unidad_Academica,
                SemaforoUnidadAcademica.Id_Formato == 2,
                SemaforoUnidadAcademica.Id_Nivel == id_nivel
            ).first()
        semaforo = 0
        if semaforo_captura:
            semaforo = semaforo_captura.Id_Semaforo
            print("Semaforo:",semaforo)
        no_validado = semaforo < 9
        print("No validado:", no_validado)
        return templates.TemplateResponse(
            "aprovechamiento_selector.html",
            {
                "rol": Rol,
                "nombre_usuario": nombre_completo,
                "periodo_activo_literal": PPeriodo,
                "periodo_anterior_literal": periodo_anterior_literal,
                "unidad_academica": UUnidad_Academica,
                "mi_unidad_sigla": UUnidad_Academica,
                "mi_unidad_id": Id_Unidad_Academica,
                "niveles": niveles,
                "request": request,
                "no_validado": True,
                "session": sess
            }
        )
    else:
        todos_los_periodos = get_todos_los_periodos(db)
        unidades_con_niveles = get_unidades_con_niveles_asociados(db)
        niveles = db.query(CatNivel).all()
        nivel_usuario = str(getattr(sess, 'nombre_nivel', '') or '')
        return templates.TemplateResponse(
            "aprovechamiento_selector.html",
            {
                "rol": Rol,
                "nombre_usuario": nombre_completo,
                "nivel_usuario": nivel_usuario,
                "periodos": todos_los_periodos,
                "periodo_activo_literal": PPeriodo,
                "periodo_activo_id": ID_PPeriodo,
                "periodo_anterior_literal": periodo_anterior_literal,
                "unidad_academica": UUnidad_Academica,
                "unidades": unidades_con_niveles,
                "niveles": niveles,
                "request": request,
                "session": sess
            }
        )


@router.post("/guardar_captura_completa")
async def guardar_captura_completa_aprovechamiento(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        print(f"📥 Datos recibidos para guardar: {data}")
        return {"message": "Captura de aprovechamiento guardada exitosamente", "status": "success"}
    except Exception as e:
        print(f"❌ Error al guardar captura completa: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al guardar captura: {str(e)}")


@router.post("/guardar_progreso_aprovechamiento")
def guardar_progreso_aprovechamiento(datos: List[Dict[str, Any]], sess=Depends(get_current_session), db: Session = Depends(get_db)):
    verificar_permiso_formato(db, usuario_id=int(sess.id_usuario), formato_id=2, id_rol=int(sess.id_rol))
    try:
        _, periodo_anterior = get_periodo_anterior_al_ultimo(db)
        if not periodo_anterior:
            print("⚠️ No se encontró un periodo anterior al último, se usará el enviado por el cliente.")
        else:
            print(f"🎯 Forzando uso de Periodo Anterior: {periodo_anterior}")

        if not datos:
            return {"message": "No hay datos para guardar"}

        mapeo_campos = {
            'periodo': 'Periodo',
            'rama': 'Nombre_Rama',
            'unidad_academica': 'Sigla',
            'sigla': 'Sigla',
            'programa': 'Nombre_Programa',
            'modalidad': 'Modalidad',
            'turno': 'Turno',
            'semestre': 'Semestre',
            'situacion_academica': 'Aprovechamiento',
            'aprovechamiento': 'Aprovechamiento',
            'sexo': 'Sexo',
            'alumnos': 'Alumnos',
            'nivel': 'Nivel',
            'id_semaforo': 'id_semaforo'
        }
        registros_procesados = 0
        errores = []

        for i, dato_original in enumerate(datos):
            try:
                dato_corregido = {}
                for key_original, value in dato_original.items():
                    key_normalizada = key_original.lower().replace(' ', '_')
                    if key_normalizada in mapeo_campos:
                        key_modelo = mapeo_campos[key_normalizada]
                        dato_corregido[key_modelo] = value

                if periodo_anterior:
                    dato_corregido['Periodo'] = periodo_anterior
                if 'Nombre_Rama' not in dato_corregido:
                    dato_corregido['Nombre_Rama'] = dato_original.get('rama', '')
                if 'id_semaforo' not in dato_corregido:
                    dato_corregido['id_semaforo'] = 2

                filtro_unico = {k: v for k, v in dato_corregido.items() if k not in ['Alumnos', 'id_semaforo']}
                if filtro_unico:
                    db.query(Temp_Aprovechamiento).filter_by(**filtro_unico).delete(synchronize_session=False)
                    db.flush()
                temp_record = Temp_Aprovechamiento(**dato_corregido)
                db.add(temp_record)
                registros_procesados += 1
                if registros_procesados % 50 == 0:
                    db.commit()
            except Exception as e:
                errores.append(f"Registro {i}: {str(e)}")
                continue

        db.commit()
        return {
            "message": f"✅ {registros_procesados} registros guardados en periodo: {periodo_anterior}",
            "registros_procesados": registros_procesados,
            "periodo_utilizado": periodo_anterior,
            "errores": errores if errores else None
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/actualizar_aprovechamiento")
async def actualizar_aprovechamiento(request: Request, sess=Depends(get_current_session), db: Session = Depends(get_db)):
    verificar_permiso_formato(db, usuario_id=int(sess.id_usuario), formato_id=2, id_rol=int(sess.id_rol))
    try:
        _, periodo_sp = get_periodo_activo(db)
        unidad_sigla = getattr(sess, 'sigla_unidad_academica')
        usuario = getattr(sess, 'usuario')
        nivel = getattr(sess, 'nombre_nivel')
        host_sp = get_request_host(request)
        print(f"🔄 EJECUTANDO SP DIRECTAMENTE PARA PERIODO: {periodo_sp}")
        sp_name = "[dbo].[SP_Actualiza_Aprovechamiento_Por_Unidad_Academica]"
        db.execute(
            text(f"""
                EXEC {sp_name}
                    @UUnidad_Academica = :unidad_academica,
                    @UUsuario = :usuario,
                    @HHost = :host,
                    @PPeriodo = :periodo,
                    @NNivel = :nivel
            """),
            {"unidad_academica": unidad_sigla, "usuario": usuario, "host": host_sp, "periodo": periodo_sp, "nivel": nivel}
        )
        db.commit()
        print(f"✅ SP {sp_name} ejecutado y commiteado exitosamente")
        return {"mensaje": "Actualización completada exitosamente", "periodo_actualizado": periodo_sp, "unidad": unidad_sigla}
    except Exception as e:
        db.rollback()
        print(f"❌ Error en actualización: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error en base de datos: {str(e)}")


@router.post("/finalizar_captura_semestre")
async def finalizar_captura_semestre(request: Request, data: Dict[str, Any], sess=Depends(get_current_session), db: Session = Depends(get_db)):
    verificar_permiso_formato(db, usuario_id=int(sess.id_usuario), formato_id=2, id_rol=int(sess.id_rol))
    try:
        unidad_sigla = (getattr(sess, 'sigla_unidad_academica', '') or '').strip()
        usuario = getattr(sess, 'usuario', '') or ''
        host = get_request_host(request)
        programa = data.get("programa", "").strip()
        modalidad = data.get("modalidad", "").strip()
        semestre = data.get("semestre", "").strip()
        _, periodo = get_periodo_activo(db)
        nivel = data.get("nivel", "").strip()

        print("\n" + "="*50)
        debug_query = f"""
        EXEC [dbo].[SP_Actualiza_Aprovechamiento_Por_Semestre_AU]
            @PPeriodo = '{periodo}',
            @UUnidad_Academica = '{unidad_sigla}',
            @MModalidad = '{modalidad}',
            @PPrograma = '{programa}',
            @SSemestre = '{semestre}',
            @UUsuario = '{usuario}',
            @HHost = '{host}',
            @NNivel = '{nivel}'
        """
        print(debug_query)
        print("="*50 + "\n")

        query = text("""
            EXEC [dbo].[SP_Actualiza_Aprovechamiento_Por_Semestre_AU]
                @PPeriodo = :periodo,
                @UUnidad_Academica = :unidad,
                @MModalidad = :modalidad,
                @PPrograma = :programa, 
                @SSemestre = :semestre,
                @UUsuario = :usuario,
                @HHost = :host,
                @NNivel = :nivel
        """)
        db.execute(query, {
            "periodo": periodo,
            "unidad": unidad_sigla,
            "modalidad": modalidad,
            "programa": programa,
            "semestre": semestre,
            "usuario": usuario,
            "host": host,
            "nivel": nivel
        })
        db.commit()

        # ── Verificar si TODOS los semestres de este nivel/UA/periodo quedaron en semáforo 3 ──
        periodo_anterior_id, _ = get_periodo_anterior_al_ultimo(db)
        ua_obj = db.query(CatUnidadAcademica).filter(CatUnidadAcademica.Sigla == unidad_sigla).first()
        nivel_obj = db.query(CatNivel).filter(CatNivel.Nivel == nivel).first()
        Id_Unidad_Academica = ua_obj.Id_Unidad_Academica if ua_obj else None
        Id_Nivel = nivel_obj.Id_Nivel if nivel_obj else None

        sp_finaliza_ejecutado = False
        if periodo_anterior_id and Id_Unidad_Academica and Id_Nivel:
            semestres_ua = db.query(SemaforoSemestreUnidadAcademica).filter(
                SemaforoSemestreUnidadAcademica.Id_Periodo == periodo_anterior_id,
                SemaforoSemestreUnidadAcademica.Id_Unidad_Academica == Id_Unidad_Academica,
                SemaforoSemestreUnidadAcademica.Id_Nivel == Id_Nivel,
                SemaforoSemestreUnidadAcademica.Id_Formato == ID_FORMATO_APROVECHAMIENTO
            ).all()
            print(f"🔍 Semestres encontrados para UA={Id_Unidad_Academica}, Nivel={Id_Nivel}, Periodo={periodo_anterior_id}: {len(semestres_ua)}")
            todos_en_tres = bool(semestres_ua) and all(s.Id_Semaforo == 3 for s in semestres_ua)
            print(f"🔍 todos_en_tres = {todos_en_tres}")

            if todos_en_tres:
                semaforoUA = db.query(SemaforoUnidadAcademica).filter(
                    SemaforoUnidadAcademica.Id_Periodo == periodo_anterior_id,
                    SemaforoUnidadAcademica.Id_Unidad_Academica == Id_Unidad_Academica,
                    SemaforoUnidadAcademica.Id_Formato == ID_FORMATO_APROVECHAMIENTO,
                    SemaforoUnidadAcademica.Id_Nivel == Id_Nivel
                ).first()
                print(f"🔍 semaforoUA = {semaforoUA}, Id_Semaforo = {semaforoUA.Id_Semaforo if semaforoUA else 'N/A'}")

                if semaforoUA and semaforoUA.Id_Semaforo == 2:
                    print(f"🚀 Todos los semestres en 3. Ejecutando SP_Finaliza_Captura_Aprovechamiento...")
                    # Obtener las combinaciones reales (Modalidad, Programa, Semestre) desde el SP de consulta
                    result_aprov = db.execute(text("""
                        SET NOCOUNT ON;
                        EXEC dbo.SP_Consulta_Aprovechamiento_Unidad_Academica
                            @UUnidad_Academica = :UUnidad_Academica,
                            @PPeriodo = :PPeriodo,
                            @NNivel = :NNivel,
                            @UUsuario = :UUsuario,
                            @HHost = :HHost;
                    """), {
                        "UUnidad_Academica": unidad_sigla,
                        "PPeriodo": periodo,
                        "NNivel": nivel,
                        "UUsuario": usuario,
                        "HHost": host,
                    })
                    aprov_rows = [dict(r) for r in result_aprov.mappings().all()] if result_aprov.returns_rows else []

                    query_finaliza = text("""
                        SET NOCOUNT ON;
                        EXEC [dbo].[SP_Finaliza_Captura_Aprovechamiento]
                            @PPeriodo = :PPeriodo,
                            @UUnidad_Academica = :UUnidad_Academica,
                            @MModalidad = :MModalidad,
                            @PPrograma = :PPrograma,
                            @SSemestre = :SSemestre,
                            @UUsuario = :UUsuario,
                            @HHost = :HHost,
                            @NNivel = :NNivel;
                    """)
                    combinaciones_procesadas = set()
                    for reg in aprov_rows:
                        m_modalidad = reg.get("Modalidad", "")
                        p_programa  = reg.get("Nombre_Programa", "")
                        s_semestre  = reg.get("Semestre", "")
                        combinacion_actual = (m_modalidad, p_programa, s_semestre)
                        if combinacion_actual not in combinaciones_procesadas:
                            combinaciones_procesadas.add(combinacion_actual)
                            db.execute(query_finaliza, {
                                "PPeriodo": periodo,
                                "UUnidad_Academica": unidad_sigla,
                                "MModalidad": m_modalidad,
                                "PPrograma": p_programa,
                                "SSemestre": s_semestre,
                                "UUsuario": usuario,
                                "HHost": host,
                                "NNivel": nivel,
                            })
                    db.commit()
                    sp_finaliza_ejecutado = True
                    print(f"✅ SP_Finaliza_Captura_Aprovechamiento ejecutado exitosamente ({len(combinaciones_procesadas)} combinaciones)")

        return {"status": "success", "message": "Proceso completado.", "sp_finaliza_ejecutado": sp_finaliza_ejecutado}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ ERROR SQL DETECTADO: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


validar_acuse = VerificarAccesoAcuse()

@router.get("/resumen-dinamico", response_class=HTMLResponse)
async def resumen_aprovechamiento_dinamico_view(
    request: Request,
    periodo: str = None,
    nivel: str = None,
    unidad_id: int = 0,
    unidad: str = None,
    sess=Depends(validar_acuse),
    db: Session = Depends(get_db)
):
    id_rol = int(getattr(sess, 'id_rol', 0) or 0)
    roles_permitidos = [1, 4, 5, 6, 7, 8, 9]
    if id_rol not in roles_permitidos:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_message": "Acceso denegado: Su rol no tiene permisos para acceder a esta funcionalidad.",
            "redirect_url": "/mod_principal/",
            "session": sess
        })

    # Forzamos los valores seguros de la sesión si vienen vacíos en la URL
    final_unidad = unidad if (unidad and unidad.strip()) else sess.sigla_unidad_academica
    final_nivel = nivel if (nivel and nivel.strip()) else sess.nombre_nivel

    # Pasamos los valores resueltos y seguros a la función del contexto
    context = await obtener_contexto_aprovechamiento(
        request, periodo, final_nivel, final_unidad, sess, db, exportando_pdf=False
    )
    context["unidad_id"] = unidad_id

    periodo_anterior_id, _ = get_periodo_anterior_al_ultimo(db)
    
    ua_obj = db.query(CatUnidadAcademica).filter(CatUnidadAcademica.Sigla == final_unidad).first()
    if not ua_obj and unidad_id:
        ua_obj = db.query(CatUnidadAcademica).filter(CatUnidadAcademica.Id_Unidad_Academica == unidad_id).first()
    Id_Unidad_Academica = ua_obj.Id_Unidad_Academica if ua_obj else int(getattr(sess, 'id_unidad_academica', 0) or 0)

    nivel_obj = db.query(CatNivel).filter(CatNivel.Nivel == final_nivel).first()
    id_nivel = nivel_obj.Id_Nivel if nivel_obj else int(getattr(sess, 'id_nivel', 0) or 0)

    semaforo_captura = db.query(SemaforoUnidadAcademica).filter(
        SemaforoUnidadAcademica.Id_Periodo          == periodo_anterior_id,
        SemaforoUnidadAcademica.Id_Unidad_Academica == Id_Unidad_Academica,
        SemaforoUnidadAcademica.Id_Formato          == 2,
        SemaforoUnidadAcademica.Id_Nivel            == id_nivel
    ).first()
    
    if semaforo_captura is None:
        no_validado = True   
    else:
        print(semaforo_captura.Id_Semaforo)
        no_validado = semaforo_captura.Id_Semaforo < 9

    print("Valor de no validado: ", no_validado)
    context["no_validado"] = no_validado
    context["unidad_id"] = Id_Unidad_Academica

    encargados = obtener_encargados(db, Id_Unidad_Academica, 2, id_nivel)
    context["nombre_capturista"] = encargados['nombre_capturista'] 
    context["nombre_ceget"] = encargados['nombre_ceget']
    context["nombre_titular"] = encargados['nombre_titular']
    context["id_unidad_academica"] = Id_Unidad_Academica

    # Retornamos pasando el diccionario 'context' limpio como segundo argumento posicional
    return templates.TemplateResponse("aprovechamiento_resumen_dinamico.html", context)


# ----------------------------------------------------------------------------
#    NUEVA VISTA: Acuse de Validación - Aprovechamiento
#    Debe estar ANTES del endpoint PDF para que Python la tenga en memoria.
# ----------------------------------------------------------------------------

validar_acuse = VerificarAccesoAcuse()

@router.get('/acuse-validacion', response_class=HTMLResponse)
async def acuse_validacion_aprovechamiento_view(
    request: Request,
    periodo: str,
    nivel: str,
    unidad: str,
    sess=Depends(validar_acuse),
    db: Session = Depends(get_db),
    exportando_pdf: bool = False,
    no_validado: bool = False,
):
    """
    Vista de Acuse de Validación - Aprovechamiento.
    Reutiliza obtener_contexto_aprovechamiento y renderiza el template.
    Accesible para roles 4-9 (validadores + directivos).
    """
    id_rol = int(getattr(sess, 'id_rol', 0) or 0)
    nombre_rol = getattr(sess, 'nombre_rol', '') or ''

    roles_permitidos = [4, 5, 6, 7, 8, 9]
    if id_rol not in roles_permitidos:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_message": f"Acceso denegado: Su rol ({nombre_rol}) no tiene permisos para generar acuses.",
            "redirect_url": "/mod_principal/"
        })

    print(f"\n{'='*70}")
    print(f"ACUSE DE VALIDACIÓN - APROVECHAMIENTO")
    print(f"{'='*70}")
    print(f"Periodo: {periodo}, Nivel: {nivel}, Unidad: {unidad}")
    print(f"Exportando PDF: {exportando_pdf}")
    print(f"{'='*70}")

    # obtener_contexto_aprovechamiento ya llama a obtener_encargados(db, Id_UA, 2)
    # y pone nombre_capturista/ceget/titular correctamente en el context.
    # No se deben sobreescribir aquí.
    context = await obtener_contexto_aprovechamiento(
        request, periodo, nivel, unidad, sess, db, exportando_pdf=exportando_pdf, no_validado=no_validado,
    )
    return templates.TemplateResponse("aprovechamiento_resumen_dinamico.html", context)


# ----------------------------------------------------------------------------
# ✅ ENDPOINT PDF - Llama a acuse_validacion_aprovechamiento_view (definida arriba)
# ----------------------------------------------------------------------------

@router.get('/acuse-validacion/pdf')
async def exportar_aprovechamiento_pdf(
    request: Request,
    periodo: str,
    nivel: str,
    unidad: str,
    no_validado: str = "false",
    sess=Depends(validar_acuse),
    db: Session = Depends(get_db),
):
    try:
        import importlib
        weasyprint = importlib.import_module("weasyprint")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"WeasyPrint no está instalado: {exc}")

    # Convertimos el parámetro string a booleano
    es_no_validado = no_validado.lower() == 'true'

    # Los nombres de capturista/CEGET/titular se obtienen internamente
    # en obtener_contexto_aprovechamiento via obtener_encargados()
    resp = await acuse_validacion_aprovechamiento_view(
        request=request,
        periodo=periodo,
        nivel=nivel,
        unidad=unidad,
        no_validado=es_no_validado,
        sess=sess,
        db=db,
        exportando_pdf=True,
    )

    if isinstance(resp, RedirectResponse):
        return resp

    if isinstance(resp.body, memoryview):
        html_text = resp.body.tobytes().decode('utf-8')
    else:
        html_text = bytes(resp.body).decode('utf-8')

    base_path = Path(__file__).resolve().parents[2] / 'frontend' / 'static'
    ruta_css  = base_path / 'css' / 'components' / 'matricula_acuse.css'

    if not ruta_css.exists():
        raise HTTPException(
            status_code=500,
            detail=f"No se encontró el CSS en: {ruta_css}."
        )

    try:
        es_esm_posgrado = ('ESM' in unidad or 'Escuela Superior de Medicina' in unidad) and ('posgrado' in nivel.lower())

        if es_esm_posgrado:
            css_content = '''
                    @page {
                        size: letter;
                        margin: 2.0cm 1.2cm 1.5cm 1.2cm;
                        @bottom-right {
                            content: "Página " counter(page) " de " counter(pages);
                            font-size: 10px;
                            font-family: Arial, sans-serif;
                            color: #636569;
                        }
                    }
                    @page :first {
                        margin-top: 1.3cm;
                    }
                    .acuse-header {
                        position: fixed !important;
                        top: -1.8cm !important;
                        left: 0 !important;
                        right: 0 !important;
                        height: 0.9cm !important;
                        text-align: center !important;
                        border-bottom: 2.5px solid #750946 !important;
                        margin: 0 !important;
                        background-color: white !important;
                        z-index: 1000 !important;
                        padding-top: 4px !important;
                    }
            '''
        else:
            css_content = '''
                    @page {
                        size: letter;
                        margin: 2.6cm 1.2cm 1.5cm 1.2cm;
                        @bottom-right {
                            content: "Página " counter(page) " de " counter(pages);
                            font-size: 10px;
                            font-family: Arial, sans-serif;
                            color: #636569;
                        }
                    }
                    @page :first {
                        margin-top: 2.3cm;
                    }
                    .acuse-header {
                        position: fixed !important;
                        top: -1.9cm !important;
                        left: 0 !important;
                        right: 0 !important;
                        height: 1.0cm !important;
                        text-align: center !important;
                        border-bottom: 2.5px solid #750946 !important;
                        margin: 0 !important;
                        background-color: white !important;
                        z-index: 1000 !important;
                        padding-top: 4px !important;
                    }
            '''

        css_content += '''
                    /* 👈 4. CSS de la Marca de agua optimizado para WeasyPrint */
                    .marca-agua {
                        position: fixed;
                        top: 45%;
                        left: 0;
                        right: 0;
                        text-align: center;
                        transform: rotate(-45deg);
                        transform-origin: center center;
                        font-size: 80px;
                        font-weight: bold;
                        color: rgba(128, 128, 128, 0.25);
                        text-transform: uppercase;
                        z-index: -1; /* Importante: z-index negativo para que quede de fondo real */
                        pointer-events: none;
                    }

                    .acciones-validacion, .panel-rechazo, .btn,
                    .estado-validacion, .mensaje-validacion {
                        display: none !important;
                    }
                    .tabla-seccion {
                        page-break-inside: avoid;
                        break-inside: avoid;
                        box-shadow: none;
                    }
                '''

        pdf_bytes = weasyprint.HTML(string=html_text, base_url=str(base_path)).write_pdf(
            stylesheets=[
                weasyprint.CSS(filename=str(ruta_css)),
                weasyprint.CSS(string=css_content)
            ]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando PDF: {str(e)}")

    filename = f"Aprovechamiento_{unidad}_{periodo}.pdf".replace(' ', '_')
    return Response(
        content=pdf_bytes,
        media_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )
# ============================================================================
# ENDPOINTS DE VALIDACIÓN / RECHAZO
# ============================================================================

@router.post("/validar")
async def validar_aprovechamiento(request: Request, sess=Depends(get_current_session), db: Session = Depends(get_db)):
    try:
        body = await request.json()
        _, periodo = get_periodo_activo(db) 
        # Panel de validación central (roles 6-9): permite elegir el periodo
        if body.get("periodo_vc"):
            periodo = str(body.get("periodo_vc")).strip()
        unidad = body.get("unidad_academica", "")
        nivel = body.get("nivel", "")
        nombre_usuario = getattr(sess, 'usuario', '') or ''
        id_rol = int(getattr(sess, 'id_rol', 0) or 0)
        host = request.client.host
        nota = body.get("nota", "Validación de aprovechamiento")
        semaforo_siguiente = SEMAFORO_SIGUIENTE.get(id_rol)

        print("Periodo Enviado al SP: " + periodo)
        if not semaforo_siguiente:
            return {"success": False, "error": "Rol no autorizado para validar."}

        # Ejecución estándar igual que roles 4 y 5
        result = db.execute(
            text("""
                SET NOCOUNT ON;
                EXEC [dbo].[SP_Valida_Aprovechamiento]
                    @PPeriodo = :periodo,
                    @UUnidad_Academica = :unidad,
                    @NNivel = :nivel,
                    @uusuario = :usuario,
                    @HHost = :host,
                    @NNota = :nota
            """),
            {"periodo": periodo, "unidad": unidad, "nivel": nivel, "usuario": nombre_usuario, "host": host, "nota": nota}
        )
        try:
            sp_rows = [dict(r) for r in result.mappings().all()]
        except Exception:
            sp_rows = []

        db.commit()

        # Enviar correo de acuse cuando el Titular (id_rol=5) valida Y todos los módulos de la UA ya están en semáforo >= 5
        acuse_info = None
        correo_acuse_enviado = False
        acuse_error = None
        correo_acuse_error = None

        if id_rol == 5:
            ua_obj = db.query(CatUnidadAcademica).filter(
                (CatUnidadAcademica.Sigla == unidad) | (CatUnidadAcademica.Nombre == unidad)
            ).first()
            id_ua = int(ua_obj.Id_Unidad_Academica) if ua_obj else int(getattr(sess, 'id_unidad_academica', 0) or 0)
            id_nivel_sess = int(getattr(sess, 'id_nivel', 0) or 0)

            # Generar y enviar acuse ÚNICAMENTE si el SP devolvió filas (autorizó la entrega de la UA)
            todos_listos = bool(sp_rows)

            if todos_listos:
                try:
                    estatus_entrega = ""
                    if sp_rows:
                        first_row = sp_rows[0]
                        for k, v in first_row.items():
                            if v and "extempor" in str(v).lower():
                                estatus_entrega = "Extemporaneo"
                                break
                            if k in ("EEntrega", "@EEntrega") and v:
                                estatus_entrega = str(v)

                    id_usuario_sess = int(getattr(sess, 'id_usuario', 0) or 0)
                    nombre_completo_sess = str(getattr(sess, 'nombre_completo', '') or nombre_usuario)
                    acuse_info, correo_acuse_enviado, acuse_error, correo_acuse_error = enviar_correo_acuse_titular(
                        db=db,
                        id_usuario=id_usuario_sess,
                        usuario_login=nombre_usuario,
                        nombre_completo=nombre_completo_sess,
                        unidad_sigla=unidad,
                        unidad_nombre=str(getattr(ua_obj, 'Nombre', '') or unidad),
                        clave_ur=str(getattr(ua_obj, 'Clave', '') or ''),
                        periodo_literal=periodo,
                        estatus_entrega=estatus_entrega,
                    )
                except Exception as _e:
                    acuse_error = str(_e)
                    print(f"❌ Error inesperado al generar acuse aprovechamiento: {_e}")
            else:
                print(f"ℹ️ Aprovechamiento validado por Titular. Aún no se genera acuse porque faltan módulos por validar en la UA ({unidad}).")

        return {
            "success": True,
            "mensaje": f"Aprovechamiento validado correctamente para {unidad} - {periodo}.",
            "correo_acuse_enviado": correo_acuse_enviado,
            "acuse": acuse_info,
            "acuse_error": acuse_error,
            "correo_acuse_error": correo_acuse_error,
        }
    except Exception as e:
        db.rollback()
        print(f"❌ Error al validar aprovechamiento: {e}")
        return {"success": False, "error": f"Error al validar aprovechamiento: {str(e)}"}


@router.post("/rechazar")
async def rechazar_aprovechamiento(request: Request, sess=Depends(get_current_session), db: Session = Depends(get_db)):
    try:
        body = await request.json()
        print("Body rechazo aprovechamiento:", body)
        _, periodo = get_periodo_activo(db) 
        # Panel de validación central (roles 6-9): permite elegir el periodo
        if body.get("periodo_vc"):
            periodo = str(body.get("periodo_vc")).strip()
        nivel = body.get("nivel", "")
        unidad = body.get("unidad_academica", "")
        motivo = body.get("motivo", "")
        nombre_usuario = getattr(sess, 'usuario', '') or ''
        id_rol = int(getattr(sess, 'id_rol', 0) or 0)
        id_unidad_objetivo = body.get("id_unidad_academica","")
        host = request.client.host
        if not motivo or len(motivo.strip()) < 10:
            return {"success": False, "error": "El motivo del rechazo debe tener al menos 10 caracteres."}
        semaforo_rechazo = SEMAFORO_RECHAZO.get(id_rol)
        if not semaforo_rechazo:
            return {"success": False, "error": "Rol no autorizado para rechazar."}

        # Ejecución estándar igual que roles 4 y 5
        db.execute(
            text("""
                SET NOCOUNT ON;
                EXEC [dbo].[SP_Rechaza_Aprovechamiento]
                    @PPeriodo = :periodo,
                    @UUnidad_Academica = :unidad,
                    @NNivel = :nivel,
                    @uusuario = :usuario,
                    @HHost = :host,
                    @NNota = :nota
            """),
            {"periodo": periodo, "unidad": unidad, "nivel": nivel, "usuario": nombre_usuario, "host": host, "nota": motivo}
        )
        db.commit()

        diccionario_correos = obtener_correos_involucrados(
            db=db, 
            id_unidad=id_unidad_objetivo, 
            id_formato = 2,
            id_nivel=body.get("id_nivel") or nivel,
            unidad_sigla=unidad,
        )
        
        print(f"📧 Correos obtenidos para notificación: {diccionario_correos}")

        notificar_rechazo_global(
           modulo_rechazado="Aprovechamiento Académico",
            id_rol_que_rechaza=id_rol,
            correos=diccionario_correos,
            unidad_academica=unidad,
        )

        return {"success": True, "mensaje": f"Aprovechamiento rechazado correctamente para {unidad} - {periodo}."}
    except Exception as e:
        db.rollback()
        print(f"❌ Error al rechazar aprovechamiento: {e}")
        return {"success": False, "error": f"Error al rechazar aprovechamiento: {str(e)}"}


@router.post("/validar_unidad_completa")
async def validar_unidad_completa(request: Request, sess=Depends(get_current_session), db: Session = Depends(get_db)):
    payload = await request.json()
    periodo = str(payload.get("periodo", "")).strip()
    unidad = str(payload.get("unidad_academica", "")).strip()
    nivel = str(payload.get("nivel", "Superior")).strip()
    usuario = str(getattr(sess, "usuario", "sistema"))
    host = get_request_host(request)
    lista = payload.get("programas", [])
    try:
        for item in lista:
            prog = str(item.get("programa", "")).strip()
            sem = str(item.get("semestre", "")).strip()
            mod = str(item.get("modalidad", "PRESENCIAL")).strip()
            if prog and sem:
                print(f"DEBUG SP: P={periodo}, U={unidad}, Prog={prog}, S={sem}")
                db.execute(
                    text("""
                        SET NOCOUNT ON;
                        EXEC [dbo].[SP_Actualiza_Aprovechamiento_Por_Semestre_AU]
                            @PPeriodo = :p,
                            @UUnidad_Academica = :u,
                            @MModalidad = :m,
                            @PPrograma = :prog, 
                            @SSemestre = :s,
                            @UUsuario = :user,
                            @HHost = :h,
                            @NNivel = :n
                    """),
                    {"p": periodo, "u": unidad, "m": mod, "prog": prog, "s": sem, "user": usuario, "h": host, "n": nivel}
                )
        db.commit()
        return {"status": "success"}
    except Exception as e:
        db.rollback()
        print(f"ERROR CRÍTICO: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": str(e)})
    
import xlsxwriter
from fastapi.responses import StreamingResponse
import io

@router.get("/exportar-excel-aprovechamiento")
async def exportar_aprovechamiento_excel(
    request: Request,
    nivel: str,
    unidad: str,
    sess=Depends(validar_acuse),
    db: Session = Depends(get_db)
):
    """
    Exporta a Excel los datos de:
    - SP_Consulta_Aprovechamiento_Unidad_Academica
    - SP_Consulta_Inscritos_Aprovechamiento
    según los filtros proporcionados.
    """
    # El SP de Aprovechamiento trabaja con el PERIODO ANTERIOR al último
    # (igual que la vista /consulta y /resumen-dinamico).
    _, periodo_sp = get_periodo_activo(db)
    if not periodo_sp:
        raise HTTPException(404, "No se encontró el periodo")
    print(f"[excel-aprovechamiento] periodo_sp='{periodo_sp}' | unidad='{unidad}' | nivel='{nivel}'")
    
    # 1. Obtener la sigla de la unidad académica (el SP espera sigla)
    ua_obj = db.query(CatUnidadAcademica).filter(
        (CatUnidadAcademica.Nombre == unidad) | (CatUnidadAcademica.Sigla == unidad)
    ).first()
    if not ua_obj:
        raise HTTPException(404, "Unidad académica no encontrada")
    sigla_unidad = ua_obj.Sigla

    usuario_login = sess.usuario
    host = request.client.host

    # 2. Ejecutar SP de aprovechamiento (igual que en /consulta)
    query_aprov = text("""
        SET NOCOUNT ON;
        EXEC dbo.SP_Consulta_Aprovechamiento_Unidad_Academica
            @UUnidad_Academica = :sigla,
            @PPeriodo = :periodo,
            @NNivel = :nivel,
            @UUsuario = :usuario,
            @HHost = :host;
    """)
    result_aprov = db.execute(query_aprov, {
        "sigla": sigla_unidad,
        "periodo": periodo_sp,
        "nivel": nivel,
        "usuario": usuario_login,
        "host": host
    })
    rows_aprovechamiento = [dict(row) for row in result_aprov.mappings().all()] if result_aprov.returns_rows else []
    rows_aprovechamiento = deduplicar_rows_aprovechamiento(rows_aprovechamiento)

    # 3. Ejecutar SP de inscritos
    query_inscritos = text("""
        SET NOCOUNT ON;
        EXEC dbo.SP_Consulta_Inscritos_Aprovechamiento
            @PPeriodo = :periodo,
            @SSigla_Unidad_Academica = :sigla,
            @NNivel = :nivel;
    """)
    result_inscritos = db.execute(query_inscritos, {
        "periodo": periodo_sp,
        "sigla": sigla_unidad,
        "nivel": nivel
    })
    rows_inscritos = [dict(row) for row in result_inscritos.mappings().all()] if result_inscritos.returns_rows else []
    rows_inscritos = deduplicar_rows_inscritos(rows_inscritos)

    # 4. Crear archivo Excel en memoria
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})

    # Hoja 1: Aprovechamiento
    ws_aprov = workbook.add_worksheet("Aprovechamiento")
    if rows_aprovechamiento:
        headers_aprov = [k for k in rows_aprovechamiento[0].keys() if str(k).lower() not in ('id_semaforo', 'id_semaforo_actual')]
        header_format = workbook.add_format({'bold': True, 'bg_color': '#750946', 'font_color': '#FFFFFF'})
        for col, h in enumerate(headers_aprov):
            ws_aprov.write(0, col, h, header_format)
        for row_idx, row in enumerate(rows_aprovechamiento, start=1):
            for col_idx, key in enumerate(headers_aprov):
                ws_aprov.write(row_idx, col_idx, row.get(key, ''))
    else:
        ws_aprov.write(0, 0, "No hay datos de aprovechamiento para los filtros seleccionados")

    # Hoja 2: Inscritos
    ws_ins = workbook.add_worksheet("Inscritos")
    if rows_inscritos:
        headers_ins = [k for k in rows_inscritos[0].keys() if str(k).lower() not in ('id_semaforo', 'id_semaforo_actual')]
        for col, h in enumerate(headers_ins):
            ws_ins.write(0, col, h)
        for row_idx, row in enumerate(rows_inscritos, start=1):
            for col_idx, key in enumerate(headers_ins):
                ws_ins.write(row_idx, col_idx, row.get(key, ''))
    else:
        ws_ins.write(0, 0, "No hay datos de inscritos para los filtros seleccionados")

    workbook.close()
    output.seek(0)

    # Nombre del archivo
    filename = f"Aprovechamiento_Inscritos_{sigla_unidad}_{nivel}_{periodo_sp}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )