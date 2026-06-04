from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
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
from backend.services.nivel_service import get_niveles_by_unidad_academica
from backend.core.auth import get_current_session

router = APIRouter()

# Variable global
HHost: str = "Test"

# Función auxiliar para obtener host
def get_request_host(request: Request) -> str:
    client_host = request.client.host if request.client else "127.0.0.1"
    return client_host

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
    'undécimo': 11, 'undecimo': 11, 'décimo primero': 11,
    'duodécimo': 12, 'duodecimo': 12, 'décimo segundo': 12,
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

def obtener_tipos_aprovechamiento(rows):
    tipos = set()
    for r in rows:
        apr = r.get("Aprovechamiento")
        if apr:
            tipos.add(str(apr).strip())
    orden_base = ['Aprobados', 'Deserción', 'Baja Definitiva', 'Baja Temporal', 'Reincorporados']
    otros = sorted([t for t in tipos if t not in orden_base])
    return orden_base + otros

# ============================================================================
# FUNCIONES DE PROCESAMIENTO DE TABLAS (TRANSPUESTAS)
# ============================================================================

def procesar_tabla_programa(rows):
    tipos_aprov = obtener_tipos_aprovechamiento(rows)
    programas = sorted({r.get("Nombre_Programa", "").strip() for r in rows if r.get("Nombre_Programa")})
    suma = defaultdict(int)
    for r in rows:
        prog = r.get("Nombre_Programa", "").strip()
        if not prog:
            continue
        apr = r.get("Aprovechamiento", "").strip()
        sexo = normalizar_sexo(r.get("Sexo", ""))
        alumnos = int(r.get("alumnos") or 0)
        suma[(prog, apr, sexo)] += alumnos

    filas = []
    for apr in tipos_aprov:
        celdas = []
        total_h_tipo = 0
        total_m_tipo = 0
        for prog in programas:
            h = suma.get((prog, apr, 'Hombre'), 0)
            m = suma.get((prog, apr, 'Mujer'), 0)
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
    for idx_prog, prog in enumerate(programas):
        h = sum(filas[idx_tipo]["celdas"][idx_prog]["h"] for idx_tipo in range(len(tipos_aprov)))
        m = sum(filas[idx_tipo]["celdas"][idx_prog]["m"] for idx_tipo in range(len(tipos_aprov)))
        totales_por_columna.append({"h": h, "m": m, "t": h + m})

    total_general_h = sum(fila["total_h"] for fila in filas)
    total_general_m = sum(fila["total_m"] for fila in filas)

    return {
        "categorias": programas,
        "filas": filas,
        "totales_por_columna": totales_por_columna,
        "total_general_h": total_general_h,
        "total_general_m": total_general_m,
        "total_general_t": total_general_h + total_general_m,
    }

def procesar_tabla_semestre(rows):
    tipos_aprov = obtener_tipos_aprovechamiento(rows)
    semestres_numeros = set()
    for r in rows:
        sem_num = semestre_texto_a_numero(r.get("Semestre"))
        if sem_num is not None and isinstance(sem_num, int):
            semestres_numeros.add(sem_num)
    semestres_ordenados = sorted(semestres_numeros)
    categorias = [str(sem) for sem in semestres_ordenados]

    suma = defaultdict(int)
    for r in rows:
        sem_num = semestre_texto_a_numero(r.get("Semestre"))
        if sem_num is None:
            continue
        apr = r.get("Aprovechamiento", "").strip()
        sexo = normalizar_sexo(r.get("Sexo", ""))
        alumnos = int(r.get("alumnos") or 0)
        suma[(sem_num, apr, sexo)] += alumnos

    filas = []
    for apr in tipos_aprov:
        celdas = []
        total_h_tipo = 0
        total_m_tipo = 0
        for sem in semestres_ordenados:
            h = suma.get((sem, apr, 'Hombre'), 0)
            m = suma.get((sem, apr, 'Mujer'), 0)
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
    for idx_sem, sem in enumerate(semestres_ordenados):
        h = sum(filas[idx_tipo]["celdas"][idx_sem]["h"] for idx_tipo in range(len(tipos_aprov)))
        m = sum(filas[idx_tipo]["celdas"][idx_sem]["m"] for idx_tipo in range(len(tipos_aprov)))
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
    exportando_pdf: bool = False
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
    nombre_ua = unidad or "—"
    periodo_activo = False
    puede_validar = False
    usuario_ya_valido = False
    usuario_ya_rechazo = False

    try:
        periodo_obj = db.query(CatPeriodo).filter(CatPeriodo.Periodo == periodo).first()
        periodo_activo = periodo_obj is not None and periodo_obj.Id_Estatus == 1

        Periodoant = get_periodo_anterior_al_ultimo(db)
        Id_Periodo_anterior = Periodoant[0] if Periodoant else None

        nivel_obj = db.query(CatNivel).filter(CatNivel.Nivel == nivel).first()
        Id_Nivel = nivel_obj.Id_Nivel if nivel_obj else None

        ua_obj = db.query(CatUnidadAcademica).filter(CatUnidadAcademica.Sigla == unidad).first()
        Id_Unidad_Academica = ua_obj.Id_Unidad_Academica if ua_obj else None

        if not exportando_pdf and id_rol in SEMAFORO_REQUERIDO and Id_Periodo_anterior and Id_Unidad_Academica and Id_Nivel:
            semaforo_actual = db.query(SemaforoUnidadAcademica).filter(
                SemaforoUnidadAcademica.Id_Periodo == Id_Periodo_anterior,
                SemaforoUnidadAcademica.Id_Unidad_Academica == Id_Unidad_Academica,
                SemaforoUnidadAcademica.Id_Formato == ID_FORMATO_APROVECHAMIENTO,
                SemaforoUnidadAcademica.Id_Nivel == Id_Nivel
            ).first()
            if semaforo_actual:
                estado_semaforo = semaforo_actual.Id_Semaforo
                semaforo_requerido = SEMAFORO_REQUERIDO.get(id_rol)
                if estado_semaforo == semaforo_requerido and periodo_activo:
                    puede_validar = True
                elif estado_semaforo >= id_rol:
                    usuario_ya_valido = True
                validacion_rechazo = db.query(Validacion).filter(
                    Validacion.Id_Periodo == Id_Periodo_anterior,
                    Validacion.Id_Usuario == id_usuario_actual,
                    Validacion.Id_Formato == ID_FORMATO_APROVECHAMIENTO,
                    Validacion.Validado == 0
                ).first()
                if validacion_rechazo and not puede_validar:
                    usuario_ya_rechazo = True
                    puede_validar = False

        resultado = db.execute(
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
        columnas = list(resultado.keys())
        rows_raw = [dict(zip(columnas, row)) for row in resultado.fetchall()]

        if not rows_raw:
            error = "No se encontraron datos para los filtros seleccionados."
        else:
            tabla_programas  = procesar_tabla_programa(rows_raw)
            tabla_semestres  = procesar_tabla_semestre(rows_raw)
            tabla_modalidades = procesar_tabla_modalidad(rows_raw)
            tabla_turnos     = procesar_tabla_turno(rows_raw)

    except Exception as e:
        import traceback
        error = f"Error al generar resumen de aprovechamiento: {e}"
        print(traceback.format_exc())

    return {
        "request": request,
        "session": sess,
        "periodo": periodo,
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
        "periodo_activo": periodo_activo,
        "puede_validar": puede_validar,
        "usuario_ya_valido": usuario_ya_valido,
        "usuario_ya_rechazo": usuario_ya_rechazo,
        "error": error,
        "exportando_pdf": exportando_pdf,
        "fecha_hoy": datetime.now().strftime("%d/%m/%Y"),
    }

# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/consulta", response_class=HTMLResponse)
def aprovechamiento_view(request: Request, sess=Depends(get_current_session), db: Session = Depends(get_db)):
    Rol = str(getattr(sess, 'nombre_rol', '') or '')
    UUsuario = getattr(sess, 'usuario', '') or ''
    UUnidad_Academica = str(getattr(sess, 'sigla_unidad_academica', '') or '')
    NNivel = str(getattr(sess, 'nombre_nivel', '') or '')
    HHost = request.client.host
    periodo_literal = get_periodo_activo(db)
    PPeriodo = periodo_literal[1]
    ID_PPeriodo = periodo_literal[0]
    periodo_aprovechamiento = PPeriodo
    Id_Unidad_Academica = int(getattr(sess, 'id_unidad_academica', 0) or 0)
    nombre_completo = getattr(sess, 'nombre_completo', '')
    periodo_anterior_id, _ = get_periodo_anterior_al_ultimo(db)

    if Rol == "Capturista":
        aprovechamientos_limpios = []
        reincorporados_detallados = []
        inscritos_final = []
        rama = ""
        id_nivel = int(sess.id_nivel)
        rechazo_info = None
        matricula_rechazada = False
        usuario_ya_valido = False
        usuario_ya_rechazo = False
        
        try:
            # ---- Obtener datos del SP de aprovechamiento ----
            query_aprov = text("""
                SET NOCOUNT ON;
                EXEC dbo.SP_Consulta_Aprovechamiento_Unidad_Academica
                    @UUnidad_Academica = :UUnidad_Academica, 
                    @PPeriodo = :PPeriodo,
                    @NNivel = :NNivel, 
                    @UUsuario = :UUsuario, 
                    @HHost = :HHost;
            """)
            result_aprov = db.execute(query_aprov, {
                "UUnidad_Academica": UUnidad_Academica,
                "PPeriodo": PPeriodo,
                "NNivel": NNivel,
                "UUsuario": UUsuario,
                "HHost": HHost
            })
            if result_aprov.returns_rows:
                aprovechamientos_raw = [dict(row) for row in result_aprov.mappings().all()]
            else:
                aprovechamientos_raw = []

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

            print(inscritos_final)
            # ---- LÓGICA DE RECHAZO (similar a matrícula) ----
            # Obtener periodo por defecto (ya existe PPeriodo)
            
            # Determinar si el último movimiento para esta UA/Periodo/Formato(2) fue rechazo
            print(f"🔑 Parámetros para rechazo:")
            print(f"   periodo_anterior_id = {periodo_anterior_id}")
            print(f"   Id_Unidad_Academica = {Id_Unidad_Academica}")
            print(f"   id_nivel (entero) = {id_nivel}")
            print(f"   Id_Formato = 2 (Aprovechamiento)")
            from backend.database.models.Usuario import Usuario
            ultimo_movimiento_ua = (
                db.query(Validacion)
                .join(Usuario, Usuario.Id_Usuario == Validacion.Id_Usuario)
                .filter(
                    Validacion.Id_Periodo == periodo_anterior_id,
                    Validacion.Id_Formato == 2,  # Formato de Aprovechamiento
                    Usuario.Id_Unidad_Academica == Id_Unidad_Academica
                )
                .order_by(Validacion.Fecha.desc())
                .first()
            )
            rechazo_vigente_ua = bool(ultimo_movimiento_ua and int(ultimo_movimiento_ua.Validado or 0) == 0)

            # Construir rechazo_info solo para capturista
            if rechazo_vigente_ua:
                ultimo_rechazo = (
                    db.query(Validacion)
                    .join(Usuario, Usuario.Id_Usuario == Validacion.Id_Usuario)
                    .filter(
                        Validacion.Id_Periodo == periodo_anterior_id,
                        Validacion.Id_Formato == 2,
                        Validacion.Validado == 0,
                        Usuario.Id_Unidad_Academica == Id_Unidad_Academica
                    )
                    .order_by(Validacion.Fecha.desc())
                    .first()
                )
                if ultimo_rechazo:
                    usuario_rechazo = db.query(Usuario).filter(Usuario.Id_Usuario == ultimo_rechazo.Id_Usuario).first()
                    nombre_rechazo = f"{usuario_rechazo.Nombre} {usuario_rechazo.Paterno} {usuario_rechazo.Materno}".strip() if usuario_rechazo else "Validador"
                    rechazo_info = {
                        'motivo': ultimo_rechazo.Nota or "Sin especificar motivo",
                        'rechazado_por': nombre_rechazo,
                        'fecha': ultimo_rechazo.Fecha.strftime("%d/%m/%Y %H:%M") if ultimo_rechazo.Fecha else ""
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
            matricula_rechazada = (not capturista_captura_completa) and rechazo_vigente_ua and (rechazo_info is not None)

            # ---- Procesamiento de datos de aprovechamiento (existente) ----
            if aprovechamientos_raw:
                todos_en_tres = all(str(reg.get("Id_Semaforo")) == "3" for reg in aprovechamientos_raw)
                print("Todos en tres:",todos_en_tres)
                if todos_en_tres:
                    print("W")
                    Periodoant = get_periodo_anterior_al_ultimo(db)
                    Id_Periodo_anterior = Periodoant[0]
                    semaforoUA = db.query(SemaforoUnidadAcademica).filter(
                        SemaforoUnidadAcademica.Id_Periodo == Id_Periodo_anterior,
                        SemaforoUnidadAcademica.Id_Unidad_Academica == Id_Unidad_Academica,
                        SemaforoUnidadAcademica.Id_Formato == 2
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
        print("antes del if")
        if semaforo_captura:
            semaforo = semaforo_captura.Id_Semaforo
            print("Semaforo:",semaforo)
        no_validado = semaforo < 9
        return templates.TemplateResponse(
            "aprovechamiento_selector.html",
            {
                "rol": Rol,
                "nombre_usuario": nombre_completo,
                "periodo_activo_literal": PPeriodo,
                "unidad_academica": UUnidad_Academica,
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
def guardar_progreso_aprovechamiento(datos: List[Dict[str, Any]], db: Session = Depends(get_db)):
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

                filtro_unico = {k: v for k, v in dato_corregido.items() if k not in ['Alumnos']}
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
        return {"status": "success", "message": "Proceso completado."}
    except Exception as e:
        db.rollback()
        print(f"❌ ERROR SQL DETECTADO: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resumen-dinamico", response_class=HTMLResponse)
async def resumen_aprovechamiento_dinamico_view(
    request: Request,
    periodo: str = "",
    nivel: str = "",
    unidad: str = "",
    sess=Depends(get_current_session),
    db: Session = Depends(get_db),
):
    context = await obtener_contexto_aprovechamiento(
        request, periodo, nivel, unidad, sess, db, exportando_pdf=False
    )
    return templates.TemplateResponse("aprovechamiento_resumen_dinamico.html", context)


# ----------------------------------------------------------------------------
# ✅ NUEVA VISTA: Acuse de Validación - Aprovechamiento
#    Debe estar ANTES del endpoint PDF para que Python la tenga en memoria.
# ----------------------------------------------------------------------------

@router.get('/acuse-validacion', response_class=HTMLResponse)
async def acuse_validacion_aprovechamiento_view(
    request: Request,
    periodo: str,
    nivel: str,
    unidad: str,
    sess=Depends(get_current_session),
    db: Session = Depends(get_db),
    exportando_pdf: bool = False,
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

    context = await obtener_contexto_aprovechamiento(
        request, periodo, nivel, unidad, sess, db, exportando_pdf=exportando_pdf
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
    sess=Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Genera el PDF del Acuse de Validación de Aprovechamiento.
    Reutiliza la vista acuse_validacion_aprovechamiento_view con exportando_pdf=True.
    """
    try:
        import importlib
        weasyprint = importlib.import_module("weasyprint")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"WeasyPrint no está instalado: {exc}")

    # ✅ acuse_validacion_aprovechamiento_view está definida ANTES, sin NameError
    resp = await acuse_validacion_aprovechamiento_view(
        request=request,
        periodo=periodo,
        nivel=nivel,
        unidad=unidad,
        sess=sess,
        db=db,
        exportando_pdf=True,
    )

    if isinstance(resp, RedirectResponse):
        return resp

    # Decodificar el HTML renderizado
    if isinstance(resp.body, memoryview):
        html_text = resp.body.tobytes().decode('utf-8')
    else:
        html_text = bytes(resp.body).decode('utf-8')

    # Ruta al CSS compartido
    base_path = Path(__file__).resolve().parents[2] / 'frontend' / 'static'
    ruta_css  = base_path / 'css' / 'components' / 'matricula_acuse.css'

    if not ruta_css.exists():
        raise HTTPException(
            status_code=500,
            detail=f"No se encontró el CSS en: {ruta_css}. Verifica que 'frontend' esté al mismo nivel que 'backend'."
        )

    try:
        pdf_bytes = weasyprint.HTML(string=html_text, base_url=str(base_path)).write_pdf(
            stylesheets=[
                weasyprint.CSS(filename=str(ruta_css)),
                weasyprint.CSS(string='''
                    @page {
                        size: landscape;
                        margin: 1cm;
                    }
                    body {
                        font-size: 9pt;
                        font-family: Arial, Helvetica, sans-serif;
                    }
                    .tabla-dinamica {
                        font-size: 7pt;
                    }
                    .tabla-dinamica th,
                    .tabla-dinamica td {
                        padding: 2px 2px !important;
                    }
                    .acciones-validacion,
                    .panel-rechazo,
                    .btn,
                    .estado-validacion,
                    .mensaje-validacion {
                        display: none !important;
                    }
                    .tabla-seccion {
                        page-break-inside: avoid;
                        break-inside: avoid;
                        box-shadow: none;
                    }
                ''')
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
        periodo = body.get("periodo", "")
        unidad = body.get("unidad_academica", "")
        nivel = body.get("nivel", "")
        nombre_usuario = getattr(sess, 'usuario', '') or ''
        id_rol = int(getattr(sess, 'id_rol', 0) or 0)
        host = request.client.host
        nota = body.get("nota", "Validación de aprovechamiento")
        semaforo_siguiente = SEMAFORO_SIGUIENTE.get(id_rol)
        if not semaforo_siguiente:
            return {"success": False, "error": "Rol no autorizado para validar."}
        db.execute(
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
        db.commit()
        return {"success": True, "mensaje": f"Aprovechamiento validado correctamente para {unidad} - {periodo}."}
    except Exception as e:
        import traceback
        db.rollback()
        return {"success": False, "error": f"Error al validar: {e}\n{traceback.format_exc()}"}


@router.post("/rechazar")
async def rechazar_aprovechamiento(request: Request, sess=Depends(get_current_session), db: Session = Depends(get_db)):
    try:
        body = await request.json()
        periodo = body.get("periodo", "")
        nivel = body.get("nivel", "")
        unidad = body.get("unidad_academica", "")
        motivo = body.get("motivo", "")
        nombre_usuario = getattr(sess, 'usuario', '') or ''
        id_rol = int(getattr(sess, 'id_rol', 0) or 0)
        host = request.client.host
        if not motivo or len(motivo.strip()) < 10:
            return {"success": False, "error": "El motivo del rechazo debe tener al menos 10 caracteres."}
        semaforo_rechazo = SEMAFORO_RECHAZO.get(id_rol)
        if not semaforo_rechazo:
            return {"success": False, "error": "Rol no autorizado para rechazar."}
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
        return {"success": True, "mensaje": f"Aprovechamiento rechazado correctamente para {unidad} - {periodo}."}
    except Exception as e:
        import traceback
        db.rollback()
        return {"success": False, "error": f"Error al rechazar: {e}\n{traceback.format_exc()}"}


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





import io
import re
import xlsxwriter
from sqlalchemy import text
from collections import defaultdict
from datetime import datetime
from fastapi.responses import StreamingResponse
from fastapi import HTTPException

@router.get("/exportar-excel-aprovechamiento")
async def exportar_aprovechamiento_excel(
    request: Request,
    periodo: str,
    nivel: str,
    unidad: str,
    sess=Depends(get_current_session),
    db: Session = Depends(get_db)
):
    try:
        from backend.database.models.CatUnidadAcademica import CatUnidadAcademica

        ua_obj = db.query(CatUnidadAcademica).filter(
            (CatUnidadAcademica.Nombre == unidad) | (CatUnidadAcademica.Sigla == unidad)
        ).first()
        if not ua_obj:
            raise HTTPException(404, "Unidad académica no encontrada")
        sigla_unidad = ua_obj.Sigla

        usuario_login = sess.usuario
        host = request.client.host

        # SP Aprovechamiento
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
            "sigla": sigla_unidad, "periodo": periodo, "nivel": nivel,
            "usuario": usuario_login, "host": host
        })
        rows_aprovechamiento = [dict(row) for row in result_aprov.mappings().all()] if result_aprov.returns_rows else []

        # SP Inscritos
        query_inscritos = text("""
            SET NOCOUNT ON;
            EXEC dbo.SP_Consulta_Inscritos_Aprovechamiento
                @PPeriodo = :periodo,
                @SSigla_Unidad_Academica = :sigla,
                @NNivel = :nivel;
        """)
        result_inscritos = db.execute(query_inscritos, {
            "periodo": periodo, "sigla": sigla_unidad, "nivel": nivel
        })
        rows_inscritos = [dict(row) for row in result_inscritos.mappings().all()] if result_inscritos.returns_rows else []

        # Detectar columna de programa
        def obtener_columna_programa(rows):
            if not rows:
                return None
            posibles = ['Nombre_Programa', 'Programa', 'NombrePrograma', 'Carrera', 'Nombre_Carrera']
            for col in posibles:
                if col in rows[0]:
                    return col
            return list(rows[0].keys())[0]

        col_prog_aprov = obtener_columna_programa(rows_aprovechamiento)
        col_prog_ins = obtener_columna_programa(rows_inscritos)

        # Agrupar
        aprov_por_programa = defaultdict(list)
        for r in rows_aprovechamiento:
            prog = r.get(col_prog_aprov, "Sin Programa") if col_prog_aprov else "Sin Programa"
            prog = str(prog).strip() or "Sin Programa"
            aprov_por_programa[prog].append(r)

        ins_por_programa = defaultdict(list)
        for r in rows_inscritos:
            prog = r.get(col_prog_ins, "Sin Programa") if col_prog_ins else "Sin Programa"
            prog = str(prog).strip() or "Sin Programa"
            ins_por_programa[prog].append(r)

        todos_programas = sorted(set(aprov_por_programa.keys()) | set(ins_por_programa.keys()))
        if not todos_programas:
            todos_programas = ["Sin programa"]

        # Crear Excel
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        # Formatos
        header_format = workbook.add_format({'bold': True, 'bg_color': '#800020', 'font_color': 'white', 'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
        data_format = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
        data_format_alt = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'bg_color': '#F9F9F9', 'text_wrap': True})
        title_format = workbook.add_format({'bold': True, 'font_size': 12, 'bg_color': '#D3D3D3', 'border': 1, 'align': 'left'})
        total_format = workbook.add_format({'bold': True, 'bg_color': '#E6E6E6', 'border': 1, 'align': 'center'})
        date_format = workbook.add_format({'italic': True, 'font_size': 9})

        fecha_actual = datetime.now().strftime("%d/%m/%Y %H:%M")

        def escribir_tabla(ws, start_row, titulo, datos, columnas_numericas=None):
            if not datos:
                ws.write(start_row, 0, f"{titulo} - Sin datos", data_format)
                return start_row + 2

            columnas = list(datos[0].keys())
            # Título
            ws.write(start_row, 0, titulo, title_format)
            ws.merge_range(start_row, 0, start_row, len(columnas)-1, titulo, title_format)
            start_row += 1
            # Encabezados
            for col, h in enumerate(columnas):
                ws.write(start_row, col, str(h), header_format)
            # Datos
            for i, row in enumerate(datos):
                fila = start_row + 1 + i
                fmt = data_format_alt if i % 2 == 0 else data_format
                for col, key in enumerate(columnas):
                    val = row.get(key, '')
                    ws.write(fila, col, str(val) if val is not None else '', fmt)
            # Autofiltro
            ws.autofilter(start_row, 0, start_row + len(datos) - 1, len(columnas)-1)
            ws.freeze_panes(start_row + 1, 0)
            # Totales
            if columnas_numericas:
                total_row = start_row + len(datos) + 1
                ws.write(total_row, 0, "TOTALES", total_format)
                for col_idx, key in enumerate(columnas):
                    if key in columnas_numericas:
                        try:
                            start_cell = xlsxwriter.utility.xl_col_to_name(col_idx) + str(start_row + 2)
                            end_cell = xlsxwriter.utility.xl_col_to_name(col_idx) + str(start_row + len(datos))
                            ws.write_formula(total_row, col_idx, f"=SUM({start_cell}:{end_cell})", total_format)
                        except:
                            pass

            # ===== AJUSTE AUTOMÁTICO DE ANCHO DE COLUMNAS =====
            for col_idx, key in enumerate(columnas):
                # Calcular longitud máxima del encabezado y de los datos
                max_len = len(str(key))
                for row in datos:
                    val = row.get(key, '')
                    cell_len = len(str(val))
                    if cell_len > max_len:
                        max_len = cell_len
                # Establecer ancho con un margen de 2 caracteres, sin límite superior
                # Si quieres un límite máximo (ej. 80), puedes usar min(max_len+2, 80)
                ws.set_column(col_idx, col_idx, max_len + 2)

            return start_row + len(datos) + 3

        # Crear hojas
        for programa in todos_programas:
            sheet_name = re.sub(r'[\\/*?:"<>|]', '_', programa)[:31]
            ws = workbook.add_worksheet(sheet_name)

            # Metadatos
            ws.write(0, 0, f"UNIDAD: {sigla_unidad}", date_format)
            ws.write(1, 0, f"PERIODO: {periodo}  |  NIVEL: {nivel}", date_format)
            ws.write(2, 0, f"FECHA EXPORTACIÓN: {fecha_actual}", date_format)
            ws.set_row(0, 15)
            ws.set_row(1, 15)
            ws.set_row(2, 15)

            current_row = 4
            aprov_data = aprov_por_programa.get(programa, [])
            col_numericas = ['Alumnos', 'Matricula', 'Total', 'Hombres', 'Mujeres', 'Grupos', 'Inscritos']
            current_row = escribir_tabla(ws, current_row, "📊 APROVECHAMIENTO", aprov_data, col_numericas)
            current_row += 1
            ins_data = ins_por_programa.get(programa, [])
            escribir_tabla(ws, current_row, "🎓 INSCRITOS", ins_data, col_numericas)

        workbook.close()
        output.seek(0)

        safe_unidad = re.sub(r'[\\/*?:"<>|]', '_', sigla_unidad)
        safe_nivel = re.sub(r'[\\/*?:"<>|]', '_', nivel)
        safe_periodo = re.sub(r'[\\/*?:"<>|]', '_', periodo)
        filename = f"Aprovechamiento_Inscritos_{safe_unidad}_{safe_nivel}_{safe_periodo}.xlsx"

        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")




