from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, Response
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import text, func
import json
from typing import List, Dict, Any, Tuple, Optional
from fastapi import HTTPException
from datetime import datetime
import time
import weasyprint

from backend.api.catalogos import semaforo
from backend.core.templates import templates
from backend.core.auth import get_current_session
from backend.database.connection import get_db
from backend.database.models.Egresados import Egresados
from backend.database.models.CatPeriodo import CatPeriodo as Periodo
from backend.database.models.CatUnidadAcademica import CatUnidadAcademica as Unidad_Academica
from backend.database.models.CatNivel import CatNivel as Nivel
from backend.database.models.CatProgramas import CatProgramas as Programas
from backend.database.models.CatModalidad import CatModalidad as Modalidad
from backend.database.models.CatTurno import CatTurno as Turno
from backend.database.models.CatBoleta import CatBoleta as Boleta
from backend.database.models.CatGeneracion import CatGeneracion as Generacion
from backend.database.models.CatSexo import CatSexo as Sexo
from backend.database.models.CatRama import CatRama as Rama
from backend.database.models.CatSemaforo import CatSemaforo
from backend.database.models.SemaforoUnidadAcademica import SemaforoUnidadAcademica
from backend.database.models.SemaforoSemestreUnidadAcademica import SemaforoSemestreUnidadAcademica
from backend.database.models.ProgramaModalidad import ProgramaModalidad
from backend.database.models.UnidadProgramaModalidad import CatUnidadProgramaModalidad
from backend.database.models.Validacion import Validacion
from backend.utils.request import get_request_host
from backend.database.models.Temp_Egresados import Temp_Egresados
from backend.database.models.CatRoles import CatRoles
from backend.services.periodo_service import get_periodo_activo, get_ultimo_periodo, get_periodo_anterior_al_ultimo
from backend.core.auth import VerificarAccesoAcuse
from backend.services.encargado_ua_service import obtener_encargados, verificar_permiso_formato
from backend.core.session_store import SessionData,session_store
from backend.database.models.Usuario import Usuario
from backend.services.envio_correo_service import (
    notificar_rechazo_global,
    obtener_correos_involucrados,
    enviar_correo_acuse_titular,
    verificar_todos_modulos_validados_titular,
)


router = APIRouter()
validar_acuse = VerificarAccesoAcuse()


def extract_unique_values_egresados(rows_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extraer valores únicos del SP de egresados para boletas, generaciones, turnos, etc.
    
    Args:
        rows_list: Lista de filas del SP como diccionarios
        
    Returns:
        Dict con estructuras únicas extraídas del SP
    """
    programas_set = set()
    modalidades_set = set()
    boletas_set = set()
    generaciones_set = set()
    turnos_set = set()
    edades_set = set()
    sexos_set = set()
    semaforos_set = set()
    
    # Mapeo de Programa -> Modalidades
    programa_modalidades = {}
    # Mapeo de (Programa, Modalidad) -> Turnos
    programa_modalidad_turnos = {}
    # Mapeo de (Programa, Modalidad) -> Boletas
    programa_modalidad_boletas = {}
    
    for row in rows_list:
        programa_nombre = None
        modalidad_nombre = None
        
        if 'Nombre_Programa' in row and row['Nombre_Programa']:
            programa_nombre = str(row['Nombre_Programa'])
            programas_set.add(programa_nombre)
        
        if 'Modalidad' in row and row['Modalidad']:
            modalidad_nombre = str(row['Modalidad'])
            modalidades_set.add(modalidad_nombre)
        
        # Crear mapeo programa -> modalidades
        if programa_nombre and modalidad_nombre:
            if programa_nombre not in programa_modalidades:
                programa_modalidades[programa_nombre] = set()
            programa_modalidades[programa_nombre].add(modalidad_nombre)
            
            if 'Turno' in row and row['Turno']:
                key_pm = f"{programa_nombre}_{modalidad_nombre}"
                if key_pm not in programa_modalidad_turnos:
                    programa_modalidad_turnos[key_pm] = set()
                programa_modalidad_turnos[key_pm].add(str(row['Turno']))
            
            # Mapeo (Programa, Modalidad) -> Boletas
            boleta_val = row.get('Boleta')
            if boleta_val is not None:
                key_pm = f"{programa_nombre}_{modalidad_nombre}"
                if key_pm not in programa_modalidad_boletas:
                    programa_modalidad_boletas[key_pm] = set()
                programa_modalidad_boletas[key_pm].add(str(boleta_val))
        
        # IMPORTANTE: usar 'is not None' en vez de truthy para no descartar el valor 0
        if 'Boleta' in row and row['Boleta'] is not None:
            boletas_set.add(str(row['Boleta']))
        
        if 'Generacion' in row and row['Generacion'] is not None:
            generaciones_set.add(str(row['Generacion']))
        
        if 'Turno' in row and row['Turno'] is not None:
            turnos_set.add(str(row['Turno']))
        
        # Intentar extraer edad de diferentes columnas posibles
        # Las edades pueden venir en formatos: "<=18", "19", "35-40", ">=65", etc.
        edad_valor = None
        if 'Grupo_Edad' in row and row['Grupo_Edad'] is not None:
            edad_valor = row['Grupo_Edad']
        elif 'Edad' in row and row['Edad'] is not None:
            edad_valor = row['Edad']
        
        if edad_valor is not None:
            # Guardar el valor tal como viene (string) sin intentar convertir
            # Esto permite rangos como "35-40", comparadores como "<=18", ">=65", y números simples
            edad_str = str(edad_valor).strip()
            if edad_str and edad_str != 'None' and edad_str != '':
                edades_set.add(edad_str)
        
        if 'Sexo' in row and row['Sexo']:
            sexos_set.add(str(row['Sexo']))
    
        if 'Estado_Semaforo' in row and row['Estado_Semaforo']:
            semaforos_set.add(str(row['Estado_Semaforo']))

    # Convertir sets de modalidades a listas ordenadas
    programa_modalidades_list = {prog: sorted(list(mods)) for prog, mods in programa_modalidades.items()}
    programa_modalidad_turnos_list = {k: sorted(list(v)) for k, v in programa_modalidad_turnos.items()}
    # Ordenar boletas descendente dentro de cada clave
    def _sort_boletas(boletas_set):
        def _key(b):
            try: return -int(b)
            except ValueError: return 0
        return sorted(list(boletas_set), key=_key)
    programa_modalidad_boletas_list = {k: _sort_boletas(v) for k, v in programa_modalidad_boletas.items()}
    
    # Ordenar edades por valor numérico, ignorando símbolos de comparación
    def ordenar_edades(edad_str):
        """Función para ordenar edades extrayendo el número principal"""
        import re
        edad_str = str(edad_str).strip()
        
        # Extraer todos los números de la cadena
        numeros = re.findall(r'\d+', edad_str)
        
        if not numeros:
            return (999, edad_str)  # Sin números, al final
        
        # Usar el primer número encontrado para ordenar
        numero_principal = int(numeros[0])
        return (numero_principal, edad_str)
    
    edades_ordenadas = sorted(list(edades_set), key=ordenar_edades)
    
    return {
        'programas': sorted(list(programas_set)),
        'modalidades': sorted(list(modalidades_set)),
        'programa_modalidades': programa_modalidades_list,
        'programa_modalidad_turnos': programa_modalidad_turnos_list,
        'programa_modalidad_boletas': programa_modalidad_boletas_list,  # NUEVO: boletas por programa+modalidad
        'boletas': sorted(list(boletas_set), reverse=True),
        'generaciones': sorted(list(generaciones_set), reverse=True),
        'turnos': sorted(list(turnos_set)),
        'edades': edades_ordenadas,
        'sexos': sorted(list(sexos_set)),
        'semaforos': sorted(list(semaforos_set))
    }


# Cache en memoria para resultados del SP de Egresados
# Estructura: cache_key -> (timestamp, (egresados_data, nota_rechazo))
_EGRESADOS_SP_CACHE: Dict[str, Tuple[float, Tuple[List[Dict[str, Any]], Optional[str]]]] = {}
_EGRESADOS_SP_CACHE_TTL = 180  # 3 minutos de validez


def invalidate_egresados_sp_cache(unidad_sigla: Optional[str] = None, periodo_literal: Optional[str] = None, nivel_nombre: Optional[str] = None):
    """
    Invalida el caché en memoria del SP de egresados.
    Si no se especifican filtros, limpia todo el caché.
    """
    global _EGRESADOS_SP_CACHE
    if unidad_sigla and periodo_literal and nivel_nombre:
        cache_key = f"{str(unidad_sigla).strip().lower()}|{str(periodo_literal).strip()}|{str(nivel_nombre).strip().lower()}"
        _EGRESADOS_SP_CACHE.pop(cache_key, None)
    else:
        _EGRESADOS_SP_CACHE.clear()


def execute_egresados_sp(
    db: Session,
    unidad_sigla: str,
    periodo_literal: str,
    nivel_nombre: str,
    usuario: str = 'sistema',
    host: str = 'localhost',
    force_refresh: bool = False
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Ejecuta el SP_Consulta_Egresados_Unidad_Academica con caché en memoria (TTL de 3 min)
    para acelerar drásticamente exportaciones a PDF y consultas consecutivas.
    
    Returns:
        Tuple[List[Dict], Optional[str]]: (datos, nota_rechazo)
    """
    cache_key = f"{str(unidad_sigla).strip().lower()}|{str(periodo_literal).strip()}|{str(nivel_nombre).strip().lower()}"
    current_time = time.time()
    
    if not force_refresh and cache_key in _EGRESADOS_SP_CACHE:
        cache_time, cached_result = _EGRESADOS_SP_CACHE[cache_key]
        if (current_time - cache_time) < _EGRESADOS_SP_CACHE_TTL:
            print(f"[egresados-sp] [CACHE] Retornando {len(cached_result[0])} registros desde CACHE en memoria para key='{cache_key}' (Exportacion ultrarrapida)")
            return cached_result
            
    try:
        # Log de parámetros que se enviarán al SP
        print(f"[egresados-sp] Ejecutando SP con parametros:")
        print(f"   @UUnidad_Academica = '{unidad_sigla}'")
        print(f"   @Pperiodo = '{periodo_literal}'")
        print(f"   @NNivel = '{nivel_nombre}'")
        print(f"   @UUsuario = '{usuario}'")
        print(f"   @HHost = '{host}'")
        
        sp_call = text("""
            EXEC SP_Consulta_Egresados_Unidad_Academica 
                @UUnidad_Academica = :unidad,
                @Pperiodo = :periodo,
                @NNivel = :nivel,
                @UUsuario = :usuario,
                @HHost = :host
        """)
        
        result = db.execute(sp_call, {
            'unidad': unidad_sigla,
            'periodo': periodo_literal,
            'nivel': nivel_nombre,
            'usuario': usuario,
            'host': host
        })
        
        # Primer resultset: datos de egresados
        rows = result.fetchall()
        columns = result.keys()
        
        egresados_data = []
        for row in rows:
            row_dict = dict(zip(columns, row))
            egresados_data.append(row_dict)
        
        # Intentar obtener nota de rechazo (segundo resultset)
        nota_rechazo = None
        try:
            # Para SQL Server, usar el cursor raw si está disponible
            if hasattr(result, 'cursor') and hasattr(result.cursor, 'nextset'):
                if result.cursor.nextset():
                    nota_rows = result.cursor.fetchall()
                    if nota_rows and len(nota_rows) > 0:
                        nota_rechazo = nota_rows[0][0] if nota_rows[0] else None
        except Exception as e_nextset:
            print(f"[egresados-sp] No se pudo obtener segundo resultset (nota rechazo): {str(e_nextset)}")
        
        # Almacenar en caché para responder inmediatamente al exportar PDF o navegar
        _EGRESADOS_SP_CACHE[cache_key] = (current_time, (egresados_data, nota_rechazo))
        return egresados_data, nota_rechazo
        
    except Exception as e:
        print(f"❌ Error ejecutando SP de egresados: {str(e)}")
        import traceback
        traceback.print_exc()
        return [], None


@router.get('/consulta')
async def captura_egresados_sp_view(request: Request, sess=Depends(validar_acuse), db: Session = Depends(get_db)):
    """
    Endpoint principal para la visualización/captura de egresados usando EXCLUSIVAMENTE Stored Procedures.
    Accesible para:
    - Rol 'Capturista' (ID 3): Captura y validación de datos
    - Roles con ID 4, 5, 6, 7, 8: Solo visualización y validación/rechazo (sin edición)
    TODA la información viene del SP, NO de los modelos ORM.
    """
    # Obtener datos del usuario logueado desde las cookies
    id_unidad_academica = int(sess.id_unidad_academica)
    
    # Manejar id_nivel que puede ser None para usuarios sin nivel (ej: directores)
    id_nivel = int(getattr(sess, 'id_nivel', 0) or 0)
    
    id_rol = int(sess.id_rol)
    nombre_rol = sess.nombre_rol
    nombre_usuario = sess.nombre_usuario
    apellidoP_usuario = sess.apellidoP_usuario
    apellidoM_usuario = sess.apellidoM_usuario
    nombre_completo = " ".join(filter(None, [nombre_usuario, apellidoP_usuario, apellidoM_usuario]))

    # ID de usuario actual (se usa para validar rechazos/validaciones)
    id_usuario_actual = int(getattr(sess, 'id_usuario', 0) or 0)

    # Validar que el usuario tenga uno de los roles permitidos
    roles_permitidos = [1, 3, 4, 5, 6, 7, 8, 9]  #1=Admin, 3=Capturista, 4-9=Roles de validación/rechazo
    if id_rol not in roles_permitidos:
        if id_rol != 0:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error_message": f"Acceso denegado: Su rol ({nombre_rol}) no tiene permisos para acceder a esta funcionalidad.",
                "redirect_url": "/mod_principal/",
                "session": sess
            })
        else:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error_message": "Acceso denegado: No se ha identificado un rol válido. Por favor, inicie sesión.",
                "redirect_url": "/login/",
                "session": sess
            })
    
    if id_rol == 3:  # Solo aplicamos la restricción al capturista
        try:
            # ID 3 corresponde a Egresados
            verificar_permiso_formato(db, usuario_id=int(sess.id_usuario), formato_id=3, id_rol=id_rol)
        except HTTPException as e:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error_message": e.detail,
                "redirect_url": "/mod_principal/",
                "session": sess
            })

    # Determinar el modo de vista según el rol
    es_capturista = (id_rol == 3)
    es_validador = (id_rol in [4, 5, 6, 7, 8, 9])  # Roles de validación/rechazo
    es_rol_director = (id_rol in [4, 5])  # Roles 4-5: Subdirector/Director - Consultan su UA con selector de nivel
    es_rol_superior = (id_rol in [6, 7, 8, 9])  # Roles 6-9: Pueden ver todas las UAs
    modo_vista = "captura" if es_capturista else "validacion"

    print(f"\n{'='*60}")
    print(f"CARGANDO VISTA DE EGRESADOS - TODO DESDE SP")
    print(f"Usuario: {nombre_completo}")
    print(f"Rol: {nombre_rol} (ID: {id_rol})")
    print(f"Modo de vista: {modo_vista.upper()}")
    print(f"Es rol superior (4-9): {es_rol_superior}")
    print(f"ID Unidad Académica: {id_unidad_academica}")
    print(f"ID Nivel: {id_nivel}")
    print(f"{'='*60}")

    # === VERIFICAR ACCESO BASADO EN SEMÁFORO (FORMATO 3 = EGRESADOS) ===
    # 1. PRIMERO: Obtener el periodo (aquí se definen periodo_default_id y literal)
    try:
        periodo_id, periodo_literal = get_periodo_activo(db)
        if not periodo_id or not periodo_literal:
            periodo_id, periodo_literal = get_ultimo_periodo(db)
        periodo_default_id = periodo_id
        periodo_default_literal = periodo_literal
        print(f"📅 Periodo activo por defecto: {periodo_default_literal} (ID: {periodo_default_id})")
        #periodo anterior al actual en string
        periodo_anterior_id, periodo_anterior_literal = get_periodo_anterior_al_ultimo(db)
        print(f"📅 Periodo anterior: {periodo_anterior_literal} (ID: {periodo_anterior_id})")

    except Exception as e:
        print(f"❌ Error al obtener periodo: {str(e)}")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_message": f"Error al cargar el periodo: {str(e)}",
            "redirect_url": "/mod_principal/",
            "session": sess
        })

    # =========================================================================
    # NUEVA LÓGICA: Buscar el ÚLTIMO estatus de validación (Formato 3 = Egresados)
    # Solo aplica para el Capturista (id_rol = 3)
    # =========================================================================
    rechazo_info = None
    matricula_rechazada = False 
        
    if es_capturista and periodo_anterior_id and id_unidad_academica and id_nivel:
        print(f"DEBUG: Consultando último movimiento de validación Egresados para PeriodoID: {periodo_anterior_id}")

        # Traemos solo el registro más reciente ordenando por fecha de mayor a menor
        ultima_validacion = db.query(Validacion).filter(
            Validacion.Id_Periodo == periodo_anterior_id,
            Validacion.Id_Unidad_Academica == id_unidad_academica,
            Validacion.Id_Nivel == id_nivel,
            Validacion.Id_Formato == 3
        ).order_by(Validacion.Fecha.desc()).first() 

        if ultima_validacion:
            # Si el campo 'Validado' es 0 (False), significa que el ÚLTIMO movimiento fue rechazo
            if ultima_validacion.Validado == 0 or ultima_validacion.Validado is False:
                
                # 1. Obtenemos datos del usuario y rol para el Frontend (Opcional, pero recomendado)
                usr_rechazo = db.query(Usuario).filter(Usuario.Id_Usuario == ultima_validacion.Id_Usuario).first()
                rol_obj = db.query(CatRoles).filter(CatRoles.Id_Rol == usr_rechazo.Id_Rol).first() if usr_rechazo else None
                
                nombre_validador = f"{usr_rechazo.Nombre} {usr_rechazo.Paterno} {usr_rechazo.Materno}".strip() if usr_rechazo else "Autoridad Validadora"
                nombre_rol_validador = rol_obj.Rol if rol_obj else "CEGET"
                fecha_format = ultima_validacion.Fecha.strftime("%d/%m/%Y %H:%M") if ultima_validacion.Fecha else "Reciente"
                
                # 2. Armar el diccionario EXACTO que el HTML de egresados espera
                rechazo_info = {
                    "motivo": ultima_validacion.Nota,
                    "rechazado_por": nombre_validador,
                    "nombre_rol": nombre_rol_validador,
                    "fecha_rechazo": fecha_format,
                    "fecha": ultima_validacion.Fecha.strftime("%d/%m/%Y") if ultima_validacion.Fecha else ""
                }
                
                # 3. Encender la bandera de rechazo
                matricula_rechazada = True
                
                print(f"DEBUG: ¡RECHAZO ACTIVO ENCONTRADO! Motivo: {rechazo_info['motivo']}")
            else:
                print("DEBUG: La captura ya está validada en verde. Se ocultan notas pasadas.")
        else:
            print("DEBUG: No hay historial de validaciones/rechazos para esta escuela.")
    else:
        print("DEBUG: Faltan datos (Periodo, UA o Nivel) para buscar validaciones.")
        # =========================================================================

    # === OBTENER INFORMACIÓN DE UNIDAD ACADÉMICA ===
    unidad_actual = None
    if (not es_rol_superior or es_rol_director) and id_unidad_academica > 0:
        unidad_actual = db.query(Unidad_Academica).filter(
            Unidad_Academica.Id_Unidad_Academica == id_unidad_academica
        ).first()
        print(f"🏫 Unidad Académica: {unidad_actual.Nombre if unidad_actual else 'No definida'}")
        
        if es_rol_director:
            print(f"👔 Rol Director (4-5): UA fija = {unidad_actual.Nombre if unidad_actual else 'N/A'}")

    # === PARA ROLES DIRECTORES (4-5) Y SUPERIORES (6-9): Cargar niveles y UAs según corresponda ===
    unidades_disponibles = []
    niveles_disponibles = []
    nivel_a_uas_json = "{}"
    periodos = []
    
    # Roles 4-5: Solo cargar niveles de su UA
    if es_rol_director:
        # Obtener todos los periodos
        periodos = db.query(Periodo).filter(Periodo.Id_Estatus == 1).order_by(Periodo.Id_Periodo.desc()).all()
        
        # Obtener niveles disponibles para esta UA desde SemaforoUnidadAcademica
        if unidad_actual:
            niveles_ua = db.query(Nivel).join(
                SemaforoUnidadAcademica,
                SemaforoUnidadAcademica.Id_Nivel == Nivel.Id_Nivel
            ).filter(
                SemaforoUnidadAcademica.Id_Unidad_Academica == id_unidad_academica,
                SemaforoUnidadAcademica.Id_Formato == 3,  # Formato 3 = Egresados
                Nivel.Id_Estatus == 1
            ).distinct().all()
            
            niveles_disponibles = [{"Id_Nivel": n.Id_Nivel, "Nivel": n.Nivel} for n in niveles_ua]
            print(f"👔 Niveles disponibles para UA {id_unidad_academica}: {[n['Nivel'] for n in niveles_disponibles]}")
    
    # Roles 6-9: Cargar todo (todos los periodos en la BD, incluidos inactivos)
    elif es_rol_superior:
        # Obtener todos los periodos disponibles en la BD
        periodos = db.query(Periodo).order_by(Periodo.Id_Periodo.desc()).all()
        
        # Obtener todos los niveles activos
        niveles_db = db.query(Nivel).filter(Nivel.Id_Estatus == 1).all()
        niveles_disponibles = [{"Id_Nivel": n.Id_Nivel, "Nivel": n.Nivel} for n in niveles_db]
        
        # Obtener todas las unidades académicas activas
        unidades_db = db.query(Unidad_Academica).filter(
            Unidad_Academica.Id_Estatus == 1
        ).order_by(Unidad_Academica.Nombre).all()
        unidades_disponibles = [{"Id_Unidad_Academica": u.Id_Unidad_Academica, "Nombre": u.Nombre, "Sigla": u.Sigla} for u in unidades_db]
        
        # Obtener relaciones Nivel-UA desde SemaforoUnidadAcademica (Formato 3 = Egresados)
        relaciones_nivel_ua = db.query(
            SemaforoUnidadAcademica.Id_Nivel,
            SemaforoUnidadAcademica.Id_Unidad_Academica
        ).filter(
            SemaforoUnidadAcademica.Id_Formato == 3  # Formato 3 = Egresados
        ).distinct().all()
        
        # Mapear Nivel a UAs (para que al seleccionar Nivel se muestren sus UAs)
        nivel_a_uas = {}
        for rel in relaciones_nivel_ua:
            id_nivel_rel = rel.Id_Nivel
            id_ua = rel.Id_Unidad_Academica
            
            if id_nivel_rel not in nivel_a_uas:
                nivel_a_uas[id_nivel_rel] = []
            if id_ua not in nivel_a_uas[id_nivel_rel]:
                nivel_a_uas[id_nivel_rel].append(id_ua)
        
        nivel_a_uas_json = json.dumps(nivel_a_uas)
        print(f"📊 Roles superiores: {len(unidades_disponibles)} UAs disponibles")
        print(f"📊 Relaciones Nivel-UA: {len(relaciones_nivel_ua)} relaciones")
        print(f"📊 Mapeo Nivel->UAs: {nivel_a_uas}")

    # === OBTENER METADATOS DEL SP PARA TODOS LOS ROLES (incluye mapeo programa→modalidad) ===
    resultados_sp = []
    programas_formatted = []
    modalidades_formatted = []
    boletas_formatted = []
    generaciones_formatted = []
    turnos_formatted = []
    edades_formatted = []
    sexos_formatted = []
    programa_a_modalidades_json = "{}"  # Mapeo programa->modalidades para filtrado dinámico
    programa_modalidad_turnos_json = "{}"  # Mapeo (programa, modalidad) -> turnos
    programa_modalidad_boletas_json = "{}"  # Mapeo (programa, modalidad) -> boletas
    datos_precargados_json = "{}"
    
    # Para roles 4-9 (directores y superiores): cargar TODAS las modalidades y programas sin ejecutar SP
    if es_rol_director or es_rol_superior:
        try:
            # Obtener TODAS las modalidades activas (sin filtrar por UA ni programa)
            modalidades_db = db.query(Modalidad).filter(
                Modalidad.Id_Estatus == 1
            ).all()
            modalidades_formatted = [{"id": m.Id_Modalidad, "nombre": m.Modalidad} for m in modalidades_db]
            print(f"🎓 Modalidades disponibles para roles 4-9: {len(modalidades_formatted)}")
            
            # Obtener TODOS los programas activos de todos los niveles
            programas_db = db.query(Programas).filter(
                Programas.Id_Estatus == 1
            ).all()
            programas_formatted = [{"id": p.Id_Programa, "nombre": p.Nombre_Programa} for p in programas_db]
            print(f"📚 Programas disponibles para roles 4-9: {len(programas_formatted)}")
            
            # Crear mapeo Programa->Modalidades desde ProgramaModalidad
            # Esto asegura que el filtrado dinámico funcione cuando el usuario seleccione UA y consulte
            from backend.database.models.ProgramaModalidad import ProgramaModalidad
            relaciones = db.query(ProgramaModalidad).filter(
                ProgramaModalidad.Id_Estatus == 1
            ).all()
            
            programa_a_modalidades = {}
            for rel in relaciones:
                if rel.Id_Programa not in programa_a_modalidades:
                    programa_a_modalidades[rel.Id_Programa] = []
                if rel.Id_Modalidad not in programa_a_modalidades[rel.Id_Programa]:
                    programa_a_modalidades[rel.Id_Programa].append(rel.Id_Modalidad)
            
            programa_a_modalidades_json = json.dumps(programa_a_modalidades)
            print(f"🔗 Mapeo Programa->Modalidad para roles 4-9: {len(programa_a_modalidades)} programas")
            
            # Para roles 4-9, NO se cargan turnos, boletas, generaciones, edades
            # Estos filtros están ocultos para roles 4-9 (solo los usa el capturista)
            # Si en el futuro se necesitan, deberían venir del SP como lo hace el rol 3
            boletas_formatted = []
            generaciones_formatted = []
            turnos_formatted = []
            sexos_formatted = []
            edades_formatted = []
            
            print(f"✅ Metadatos cargados para roles 4-9 SIN ejecutar SP")
            print(f"⏳ El SP se ejecutará cuando el usuario haga clic en 'Consultar Egresados'")
            
        except Exception as e:
            print(f"❌ Error al cargar metadatos para roles 4-9: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # Para rol 3 (capturista) ÚNICAMENTE: cargar desde el SP de su UA específica
    elif es_capturista and id_nivel > 0 and id_unidad_academica > 0:
        print(f"🔄 Rol Capturista detectado - Ejecutando SP inmediatamente para cargar datos iniciales...")
        try:
            # Obtener datos necesarios para el SP
            nivel = db.query(Nivel).filter(Nivel.Id_Nivel == id_nivel).first()
            nivel_nombre = nivel.Nivel if nivel else ""
            
            # Para egresados, usar el periodo actual (el último/default)
            periodo_para_sp = periodo_default_literal
            print(f"📅 Usando periodo para SP de egresados: {periodo_para_sp}")

            # Ejecutar SP para obtener metadatos
            resultados_sp, _ = execute_egresados_sp(
                db=db,
                unidad_sigla=unidad_actual.Sigla if unidad_actual else "",
                periodo_literal=periodo_para_sp,
                nivel_nombre=nivel_nombre,
                usuario=nombre_completo,
                host=get_request_host(request)
            )
            
            if resultados_sp:
                # Extraer valores únicos del SP
                valores_unicos = extract_unique_values_egresados(resultados_sp)
                
                print(f"📊 METADATOS EXTRAÍDOS DEL SP:")
                print(f"   Programas: {valores_unicos.get('programas', [])}")
                print(f"   Modalidades: {valores_unicos.get('modalidades', [])}")
                print(f"   Boletas: {valores_unicos.get('boletas', [])}")
                print(f"   Generaciones: {valores_unicos.get('generaciones', [])}")
                print(f"   Turnos: {valores_unicos.get('turnos', [])}")
                print(f"   Edades: {valores_unicos.get('edades', [])}")
                print(f"   Sexos: {valores_unicos.get('sexos', [])}")
                print(f"   Mapeo Programa->Modalidades: {valores_unicos.get('programa_modalidades', {})}")

                # Mapear Semáforos si es necesario
                semaforos_sp = valores_unicos.get('semaforos', [])
                if semaforos_sp:
                    print(f"✅ Semáforos detectados del SP: {semaforos_sp}")
                
                # Mostrar id_semaforo de cada registro del SP
                print(f"\n Valores de id_semaforo en resultados_sp:")
                semaforos_raw = set()
                for idx, reg in enumerate(resultados_sp[:10]):  # Primeros 10 registros
                    id_sem = reg.get('Id_Semaforo') or reg.get('id_semaforo') or reg.get('ID_SEMAFORO')
                    print(f"   Registro {idx+1}: Id_Semaforo = {id_sem} ")
                    if id_sem is not None:
                        semaforos_raw.add(id_sem)
                print(f"   Total registros del SP: {len(resultados_sp)}")
                print(f"   Valores únicos de Id_Semaforo encontrados: {semaforos_raw}\n")
                
                # Mapear Programas
                programas_sp = valores_unicos.get('programas', [])
                if programas_sp:
                    programas_db = db.query(Programas).filter(
                        Programas.Nombre_Programa.in_(programas_sp),
                        Programas.Id_Nivel == id_nivel,
                        Programas.Id_Estatus == 1
                    ).all()
                    programas_formatted = [{"id": p.Id_Programa, "nombre": p.Nombre_Programa} for p in programas_db]
                    print(f"Programas mapeados ({len(programas_formatted)}): {[p['nombre'] for p in programas_formatted]}")
                
                # Mapear Modalidades
                modalidades_sp = valores_unicos.get('modalidades', [])
                if modalidades_sp:
                    modalidades_db = db.query(Modalidad).filter(
                        Modalidad.Modalidad.in_(modalidades_sp),
                        Modalidad.Id_Estatus == 1
                    ).all()
                    modalidades_formatted = [{"id": m.Id_Modalidad, "nombre": m.Modalidad} for m in modalidades_db]
                    print(f"Modalidades mapeadas ({len(modalidades_formatted)}): {[m['nombre'] for m in modalidades_formatted]}")
                
                # Mapear Boletas
                boletas_sp = valores_unicos.get('boletas', [])
                if boletas_sp:
                    boletas_db = db.query(Boleta).filter(
                        Boleta.Boleta.in_(boletas_sp),
                        Boleta.Id_Estatus == 1
                    ).order_by(Boleta.Boleta.desc()).all()

                    # Construir mapa por nombre para lookup O(1)
                    boletas_db_map = {str(b.Boleta).strip(): b for b in boletas_db}

                    # Mantener el orden descendente del SP e incluir las que no están en BD
                    boletas_formatted = []
                    for sp_bol in boletas_sp:  # Ya viene ordenado descendente desde extract_unique_values
                        sp_bol_str = str(sp_bol).strip()
                        if sp_bol_str in boletas_db_map:
                            b = boletas_db_map[sp_bol_str]
                            boletas_formatted.append({"id": b.Id_Boleta, "nombre": str(b.Boleta)})
                        else:
                            # Boleta del SP sin entrada en Cat_Boleta → usar valor raw
                            boletas_formatted.append({"id": sp_bol_str, "nombre": sp_bol_str})
                            print(f"⚠️ Boleta '{sp_bol_str}' del SP no encontrada en Cat_Boleta → incluida con valor raw")

                    print(f"Boletas mapeadas ({len(boletas_formatted)}): {[b['nombre'] for b in boletas_formatted]}")
                
                # Mapear Generaciones
                generaciones_sp = valores_unicos.get('generaciones', [])
                if generaciones_sp:
                    generaciones_db = db.query(Generacion).filter(
                        Generacion.Generacion.in_(generaciones_sp),
                        Generacion.Id_Estatus == 1
                    ).order_by(Generacion.Generacion.desc()).all()
                    generaciones_formatted = [{"id": g.Id_Generacion, "nombre": g.Generacion} for g in generaciones_db]
                    print(f"Generaciones mapeadas ({len(generaciones_formatted)}): {[g['nombre'] for g in generaciones_formatted]}")
                
                # Mapear Turnos
                turnos_sp = valores_unicos.get('turnos', [])
                if turnos_sp:
                    turnos_db = db.query(Turno).filter(
                        Turno.Turno.in_(turnos_sp),
                        Turno.Id_Estatus == 1
                    ).all()
                    turnos_db_map = {str(t.Turno).strip().lower(): t for t in turnos_db}
                    turnos_formatted = []
                    for t_nom in turnos_sp:
                        t_nom_str = str(t_nom).strip()
                        t_obj = turnos_db_map.get(t_nom_str.lower())
                        if t_obj:
                            turnos_formatted.append({"id": t_obj.Id_Turno, "nombre": t_obj.Turno})
                        else:
                            turnos_formatted.append({"id": t_nom_str, "nombre": t_nom_str})
                    print(f"Turnos mapeados ({len(turnos_formatted)}): {[t['nombre'] for t in turnos_formatted]}")
                else:
                    turnos_formatted = []
                
                # Mapear Sexos (Opcional, si el SP los retorna)
                sexos_db = db.query(Sexo).filter(Sexo.Id_Estatus == 1).all()
                sexos_formatted = [{"id": s.Id_Sexo, "nombre": s.Sexo} for s in sexos_db]
                print(f"Sexos disponibles: {[s['nombre'] for s in sexos_formatted]}")
                
                # Extraer edades del SP (pueden venir como números, rangos o comparadores)
                edades_sp = valores_unicos.get('edades', [])
                if edades_sp:
                    # Usar el string como ID y nombre (soporta "<=18", "35-40", ">=65", etc.)
                    edades_formatted = [{"id": edad, "nombre": edad} for edad in edades_sp]
                    print(f"Edades mapeadas ({len(edades_formatted)}): {edades_sp}")
                else:
                    edades_formatted = []
                
                # Crear mapeo de ID_Programa -> [ID_Modalidad] para filtrado dinámico
                programa_modalidades_map = valores_unicos.get('programa_modalidades', {})
                programa_a_modalidades = {}  # {id_programa: [id_modalidad, ...]}
                
                for prog_db in programas_formatted:
                    prog_nombre = prog_db["nombre"]
                    if prog_nombre in programa_modalidades_map:
                        modalidades_del_programa = programa_modalidades_map[prog_nombre]
                        ids_modalidades = [m["id"] for m in modalidades_formatted if m["nombre"] in modalidades_del_programa]
                        programa_a_modalidades[prog_db["id"]] = ids_modalidades
                
                programa_a_modalidades_json = json.dumps(programa_a_modalidades)
                print(f"Mapeo ID_Programa -> IDs_Modalidad: {programa_a_modalidades_json}")

                programa_modalidad_turnos_json = json.dumps(valores_unicos.get('programa_modalidad_turnos', {}))
                print(f"Mapeo (Programa, Modalidad) -> Turnos: {programa_modalidad_turnos_json}")

                programa_modalidad_boletas_json = json.dumps(valores_unicos.get('programa_modalidad_boletas', {}))
                print(f"Mapeo (Programa, Modalidad) -> Boletas: {programa_modalidad_boletas_json}")

                datos_precargados = {}
                for reg in resultados_sp:
                    # Extraer textos limpios
                    # IMPORTANTE: usar `if X is not None else ''` para no perder el valor 0 (falsy en Python)
                    prog_val = str(reg.get('Nombre_Programa') or '').strip()
                    mod_val  = str(reg.get('Modalidad') or '').strip()
                    bol_raw  = reg.get('Boleta')
                    bol_val  = str(bol_raw if bol_raw is not None else '').strip()
                    gen_raw  = reg.get('Generacion')
                    gen_val  = str(gen_raw if gen_raw is not None else '').strip()
                    edad_raw = reg.get('Grupo_Edad') if reg.get('Grupo_Edad') is not None else reg.get('Edad')
                    edad_val = str(edad_raw if edad_raw is not None else '').strip()
                    
                    # Llave única idéntica a la del Frontend
                    key = f"{prog_val}_{mod_val}_{bol_val}_{gen_val}_{edad_val}"
                    if key not in datos_precargados:
                        datos_precargados[key] = {}
                    
                    turno_raw    = reg.get('Turno')
                    turno_nombre = str(turno_raw if turno_raw is not None else '').strip()
                    if turno_nombre not in datos_precargados[key]:
                        datos_precargados[key][turno_nombre] = {'hombres': '', 'mujeres': ''}
                    
                    sexo_str = str(reg.get('Sexo') or '').lower()
                    try:
                        # Si hay un número de egresados, lo guardamos
                        egresados_val = reg.get('Egresados')
                        if egresados_val is not None and str(egresados_val).strip() != '':
                            egresados_val = int(float(egresados_val))
                            if 'hombre' in sexo_str or sexo_str == 'h':
                                datos_precargados[key][turno_nombre]['hombres'] = egresados_val
                            else:
                                datos_precargados[key][turno_nombre]['mujeres'] = egresados_val
                    except Exception:
                        pass # Si no es un número válido, se ignora
                        
                datos_precargados_json = json.dumps(datos_precargados)

            else:
                # Si el SP no retorna datos, dejar todo vacío
                print(f"   El SP no retornó datos para esta UA/Nivel/Periodo")
                print(f"   No se cargarán programas ni modalidades (esperando datos del SP)")
                programas_formatted = []
                modalidades_formatted = []
                boletas_formatted = []
                generaciones_formatted = []
                turnos_formatted = []
                sexos_formatted = []
                edades_formatted = []
                programa_a_modalidades_json = "{}"
                programa_modalidad_turnos_json = "{}"
                programa_modalidad_boletas_json = "{}"
                    
        except Exception as e:
            print(f"❌ Error al obtener metadatos del SP: {str(e)}")
            import traceback
            traceback.print_exc()

    # Obtener datos del semáforo para las pestañas de turnos (primeros 3 registros)
    semaforo_estados = db.query(CatSemaforo).filter(CatSemaforo.Id_Semaforo.in_([1, 2, 3])).order_by(CatSemaforo.Id_Semaforo).all()
    semaforo_data = []
    for estado in semaforo_estados:
        # Asegurar que el color tenga el símbolo # al inicio
        color = estado.Color_Semaforo
        if color and not color.startswith('#'):
            color = f"#{color}"
        
        semaforo_data.append({
            'id': estado.Id_Semaforo,
            'descripcion': estado.Descripcion_Semaforo,
            'color': color
        })
    
    print(f" Estados del semáforo cargados: {len(semaforo_data)}")
    for estado in semaforo_data:
        print(f"  - ID {estado['id']}: {estado['descripcion']} ({estado['color']})")

    # === LÓGICA DE SEMÁFORO PARA BOTONES DE VALIDACIÓN ===
    usuario_ya_valido = False
    usuario_ya_rechazo = False
    puede_validar = False

    if id_nivel == 0 and len(niveles_disponibles) > 0:
        id_nivel = niveles_disponibles[0]["Id_Nivel"]
        print(f"🔄 Nivel auto-asignado para validación de semáforo: {id_nivel}")
    
    # Consultar semáforo para esta UA/Periodo/Nivel/Formato=3 (Egresados)
    semaforo_unidad = db.query(SemaforoUnidadAcademica).filter(
        SemaforoUnidadAcademica.Id_Unidad_Academica == id_unidad_academica,
        SemaforoUnidadAcademica.Id_Periodo == periodo_anterior_id,
        SemaforoUnidadAcademica.Id_Nivel == id_nivel,
        SemaforoUnidadAcademica.Id_Formato == 3  # Formato 3 = Egresados
    ).first()
    
    if semaforo_unidad:
        estado_semaforo = semaforo_unidad.Id_Semaforo
        print(f"   📊 Estado del semáforo egresados: {estado_semaforo}")
        
        # Lógica: El usuario puede validar si el semáforo está en (id_rol - 1)
        semaforo_esperado = id_rol - 1
        print(f"   ⚖️ Semáforo esperado para rol {id_rol}: {semaforo_esperado}")
        
        if estado_semaforo == semaforo_esperado:
            puede_validar = True
            print(f"   ✅ Usuario PUEDE validar egresados (semáforo en nivel correcto)")
        elif estado_semaforo >= id_rol:
            usuario_ya_valido = True
            print(f"   🔒 Usuario YA validó egresados (semáforo >= {id_rol})")
        else:
            print(f"   ⏳ Usuario debe esperar (semáforo en nivel {estado_semaforo})")
    else:
        print(f"   ⚠️ No se encontró semáforo egresados para esta UA/Nivel/Periodo")
    
    # Verificar si el usuario rechazó estos egresados
    validacion_rechazo = db.query(Validacion).filter(
        Validacion.Id_Periodo == periodo_default_id,
        Validacion.Id_Usuario == id_usuario_actual,
        Validacion.Id_Formato == 3,  # Formato 3 = Egresados
        Validacion.Validado == 0  # Rechazo
    ).first()
    
    if validacion_rechazo:
        if not (semaforo_unidad and estado_semaforo == (id_rol - 1)):
            usuario_ya_rechazo = True
            print(f"   ❌ Usuario YA rechazó estos egresados")
    
    print(f"\n📤 Estado de validación egresados:")
    print(f"   puede_validar: {puede_validar}")
    print(f"   usuario_ya_valido: {usuario_ya_valido}")
    print(f"   usuario_ya_rechazo: {usuario_ya_rechazo}")
    
    # Renderizar la plantilla - usar egresados_consulta_limpio.html para todos los roles
    template_name = "egresados_consulta_limpio.html"
    
    print(f"Renderizando template: {template_name}")

    return templates.TemplateResponse(template_name, {
        "request": request,
        "nombre_usuario": nombre_completo,
        "nombre_rol": nombre_rol,
        "id_rol": id_rol,
        "periodo_default_id": periodo_default_id,
        "periodo_default_literal": periodo_default_literal,
        "periodo_anterior_literal": periodo_anterior_literal,
        "unidad_actual": unidad_actual,
        "programas": programas_formatted,
        "modalidades": modalidades_formatted,
        "boletas": boletas_formatted,
        "generaciones": generaciones_formatted,
        "turnos": turnos_formatted,
        "edades": edades_formatted,
        "sexos": sexos_formatted,
        "es_capturista": es_capturista,
        "es_validador": es_validador,
        "es_rol_director": es_rol_director,
        "es_rol_superior": es_rol_superior,
        "unidades_disponibles": unidades_disponibles,
        "niveles_disponibles": niveles_disponibles,
        "nivel_a_uas_json": nivel_a_uas_json,
        "programa_a_modalidades_json": programa_a_modalidades_json,
        "programa_modalidad_turnos_json": programa_modalidad_turnos_json,
        "programa_modalidad_boletas_json": programa_modalidad_boletas_json,
        "semaforo_estados": semaforo_data,
        "periodos": periodos,
        "rechazo_info": rechazo_info,
        "matricula_rechazada": matricula_rechazada,
        "acceso_restringido": False,
        "puede_validar": puede_validar,
        "usuario_ya_valido": usuario_ya_valido,
        "usuario_ya_rechazo": usuario_ya_rechazo,
        "datos_precargados_json": datos_precargados_json,
        "filas": resultados_sp if resultados_sp else [],
        "session": sess
    })


@router.post('/consultar')
async def consultar_egresados(request: Request, sess=Depends(get_current_session), db: Session = Depends(get_db)):
    """
    Ejecuta el SP_Consulta_Egresados_Unidad_Academica para obtener datos de egresados
    """
    verificar_permiso_formato(db, usuario_id=int(sess.id_usuario), formato_id=3, id_rol=int(sess.id_rol))
    try:
        data = await request.json()

        id_periodo = data.get('id_periodo')
        id_unidad_academica = data.get('id_unidad_academica') or getattr(sess, 'id_unidad_academica', None)
        id_nivel = data.get('id_nivel') or getattr(sess, 'id_nivel', None)
        id_programa = data.get('id_programa')
        id_modalidad = data.get('id_modalidad')

        # Obtener información desde sesión
        nombre_usuario = sess.nombre_usuario
        apellidoP_usuario = sess.apellidoP_usuario
        apellidoM_usuario = sess.apellidoM_usuario
        nombre_completo = " ".join(filter(None, [nombre_usuario, apellidoP_usuario, apellidoM_usuario]))
        host = get_request_host(request)

        # Obtener datos de periodo, unidad y nivel
        periodo = db.query(Periodo).filter(Periodo.Id_Periodo == id_periodo).first()
        unidad = None
        try:
            if id_unidad_academica is not None:
                unidad = db.query(Unidad_Academica).filter(
                    Unidad_Academica.Id_Unidad_Academica == int(id_unidad_academica)
                ).first()
        except Exception:
            unidad = None

        nivel = None
        try:
            nivel = db.query(Nivel).filter(Nivel.Id_Nivel == int(id_nivel)).first()
        except Exception:
            nivel = None

        if not all([periodo, unidad, nivel]):
            raise HTTPException(status_code=400, detail="Faltan datos requeridos: periodo, unidad o nivel")

        unidad_sigla = unidad.Sigla
        periodo_literal = periodo.Periodo
        nivel_nombre = nivel.Nivel

        print(f"\n{'='*60}")
        print(f"📊 EJECUTANDO SP DE CONSULTA DE EGRESADOS")
        print(f"Usuario: {nombre_completo}")
        print(f"Periodo: {periodo_literal} (ID: {id_periodo})")
        print(f"Unidad Académica: {unidad.Nombre} (ID: {id_unidad_academica})")
        print(f"Nivel: {nivel_nombre} (ID: {id_nivel})")
        print(f"{'='*60}")

        sp_call = text("""
            EXEC SP_Consulta_Egresados_Unidad_Academica 
                @UUnidad_Academica = :unidad,
                @Pperiodo = :periodo,
                @NNivel = :nivel,
                @UUsuario = :usuario,
                @HHost = :host
        """)

        result = db.execute(sp_call, {
            'unidad': unidad_sigla,
            'periodo': periodo_literal,
            'nivel': nivel_nombre,
            'usuario': nombre_completo,
            'host': host
        })

        rows = result.fetchall()
        columns = result.keys()

        egresados_data = [dict(zip(columns, row)) for row in rows]

        if id_programa:
            programa = db.query(Programas).filter(Programas.Id_Programa == id_programa).first()
            if programa:
                egresados_data = [e for e in egresados_data if e.get('Nombre_Programa') == programa.Nombre_Programa]

        if id_modalidad:
            modalidad = db.query(Modalidad).filter(Modalidad.Id_Modalidad == id_modalidad).first()
            if modalidad:
                egresados_data = [e for e in egresados_data if e.get('Modalidad') == modalidad.Modalidad]

        print(f"✅ Consulta exitosa: {len(egresados_data)} registros encontrados")

        return {"success": True, "data": egresados_data, "count": len(egresados_data)}

    except Exception as e:
        print(f"❌ Error al consultar egresados: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

    # Fin consultar

@router.post('/guardar')
async def guardar_egresados(request: Request, sess=Depends(get_current_session), db: Session = Depends(get_db)):
    verificar_permiso_formato(db, usuario_id=int(sess.id_usuario), formato_id=3, id_rol=int(sess.id_rol))
    try:
        data = await request.json()
        registros = data.get('registros', [])
        periodo_id = data.get('id_periodo') or data.get('periodo')
        
        if not periodo_id:
            raise HTTPException(status_code=400, detail="Faltan parámetros requeridos: periodo")

        # 1. PRECARGA MASIVA (Evita consultas N+1)
        programas_dict = {p.Id_Programa: p for p in db.query(Programas).all()}
        modalidades_dict = {m.Id_Modalidad: m for m in db.query(Modalidad).all()}
        boletas_dict = {b.Id_Boleta: b for b in db.query(Boleta).all()}
        generaciones_dict = {g.Id_Generacion: g for g in db.query(Generacion).all()}
        turnos_dict = {t.Id_Turno: t for t in db.query(Turno).all()}
        ramas_dict = {r.Id_Rama: r.Nombre_Rama for r in db.query(Rama).all()}

        # 2. RESOLVER CONTEXTO (UA, Período, Nivel)
        unidad_obj = db.query(Unidad_Academica).filter(Unidad_Academica.Id_Unidad_Academica == int(sess.id_unidad_academica)).first()
        nivel_obj = db.query(Nivel).filter(Nivel.Id_Nivel == int(sess.id_nivel)).first()
        
        # ⚠️ IMPORTANTE: DOS periodos diferentes
        # 1. periodo_texto_actual: para CONSULTAR datos desde SP_Consulta_Egresados_Unidad_Academica (el periodo enviado)
        # 2. periodo_texto_temp: para GUARDAR en Temp_Egresados (el periodo anterior)
        
        # Periodo actual (para consultar SP)
        periodo_obj_actual = db.query(Periodo).filter(Periodo.Id_Periodo == int(periodo_id)).first()
        if not periodo_obj_actual:
            raise HTTPException(status_code=400, detail=f"No existe periodo con Id={periodo_id}")
        periodo_texto_actual = periodo_obj_actual.Periodo
        print(f"📅 Periodo ACTUAL (para consultar SP): {periodo_texto_actual} (Id={periodo_id})")
        
        # Periodo anterior (para guardar en Temp_Egresados)
        periodo_anterior_id = int(periodo_id) - 1
        periodo_obj_anterior = db.query(Periodo).filter(Periodo.Id_Periodo == periodo_anterior_id).first()
        if not periodo_obj_anterior:
            raise HTTPException(
                status_code=400, 
                detail=f"No existe periodo anterior (Id={periodo_anterior_id}). Periodo recibido era {periodo_id}"
            )
        periodo_texto_temp = periodo_obj_anterior.Periodo
        print(f"📅 Periodo ANTERIOR (para guardar Temp): {periodo_texto_temp} (Id={periodo_anterior_id})")

        # 3. LIMPIEZA PREVIA (Muy importante para no duplicar avance)
        db.query(Temp_Egresados).filter(
            Temp_Egresados.Sigla == unidad_obj.Sigla,
            Temp_Egresados.Periodo == periodo_texto_temp
        ).delete()

        # 4. PROCESAMIENTO EN MEMORIA
        objetos_a_guardar = []

        # Si el front envía registros, los usamos; si no, intentamos obtenerlos desde el SP de consulta
        registros_origen = registros
        if not registros_origen:
            try:
                print("🔄 No se recibieron registros en el payload, obteniendo datos desde SP_Consulta_Egresados_Unidad_Academica...")
                resultados_sp, _ = execute_egresados_sp(
                    db=db,
                    unidad_sigla=unidad_obj.Sigla if unidad_obj else '',
                    periodo_literal=periodo_texto_actual,  # ← USAR PERIODO ACTUAL PARA CONSULTAR SP
                    nivel_nombre=nivel_obj.Nivel if nivel_obj else '',
                    usuario=str(sess.nombre_usuario),
                    host=get_request_host(request)
                )
                registros_origen = resultados_sp or []
                print(f"🔍 Registros obtenidos desde SP: {len(registros_origen)}")
            except Exception as e_sp:
                print(f"⚠️ No se pudieron obtener registros desde SP: {str(e_sp)}")
                registros_origen = []

        print(f"📥 /guardar payload: registros recibidos={len(registros_origen)} | periodo_temp={periodo_texto_temp} | sigla={unidad_obj.Sigla if unidad_obj else 'N/A'}")
        
        # 🔍 INSPECCIÓN DETALLADA DE REGISTROS RECIBIDOS
        if registros_origen:
            print(f"\n🔎 INSPECCIÓN DETALLADA de primeros 3 registros:")
            for idx, reg in enumerate(registros_origen[:3]):
                print(f"\n   Registro[{idx}]:")
                print(f"   - Keys: {list(reg.keys())}")
                for key in reg.keys():
                    print(f"   - {key}: '{reg.get(key)}'")
        else:
            print("⚠️ ¡Registros vacío!")

        def _safe_int(valor, default=0):
            try:
                if valor is None:
                    return default
                txt = str(valor).strip()
                if txt == '':
                    return default
                return int(float(txt))
            except Exception:
                return default

        # Procesar registros: todos los registros VIENEN DEL SP en formato textual
        # Solo hay que copiar campos textuales y reemplazar Egresados con la cantidad del usuario
        for idx, reg in enumerate(registros_origen):
            try:
                # 🔍 DETECTAR FORMATO: ¿Viene del frontend o del SP?
                es_formato_frontend = 'programaNombre' in reg or 'modalidadNombre' in reg or 'turnos' in reg
                es_formato_sp = 'Nombre_Programa' in reg or 'Modalidad' in reg
                
                if es_formato_frontend:
                    # ========================
                    # FORMATO FRONTEND
                    # ========================
                    print(f"\n🎨 FRONTEND FORMAT detectado en registro[{idx}]")
                    
                    # Mapear campos frontend → SP
                    nombre_programa = str(reg.get('programaNombre') or '')
                    nombre_rama = ''  # Frontend no lo envía, lo resolvemos por programa
                    nivel_sp = nivel_obj.Nivel if nivel_obj else ''
                    modalidad = str(reg.get('modalidadNombre') or '')
                    grupo_edad = str(reg.get('edadNombre') or reg.get('edad') or '')
                    boleta = str(reg.get('boletaNombre') or '')
                    generacion = str(reg.get('generacionNombre') or '')
                    
                    # ⚠️ IMPORTANTE: El frontend envía turnos como JSON
                    # Estructura: {"1": {"hombres": 200, "mujeres": 0}, "2": {"hombres": 0, "mujeres": 0}}
                    # Debo crear UNA FILA por cada turno+sexo+cantidad > 0
                    turnos_data = reg.get('turnos', '{}')
                    if isinstance(turnos_data, str):
                        try:
                            import json
                            turnos_data = json.loads(turnos_data)
                        except Exception as e_json:
                            print(f"⚠️ Error parseando JSON de turnos: {str(e_json)}")
                            turnos_data = {}
                    
                    print(f"   Parseado turnos_data: {turnos_data}")
                    
                    # Para cada turno disponible
                    for turno_id, sexos_dict in turnos_data.items():
                        # Resolver turno ID → nombre (soporta ID entero o string como 'Matutino', 'Vespertino', etc.)
                        turno_obj = None
                        if str(turno_id).isdigit():
                            turno_obj = turnos_dict.get(int(turno_id)) or db.query(Turno).filter(Turno.Id_Turno == int(turno_id)).first()
                        if not turno_obj:
                            turno_obj = db.query(Turno).filter(Turno.Turno == str(turno_id)).first()
                        turno_nombre = turno_obj.Turno if turno_obj else str(turno_id)
                        
                        # Para cada sexo en ese turno
                        for sexo_label, cantidad_raw in sexos_dict.items():
                            cantidad = _safe_int(cantidad_raw, 0)
                            
                            # Resolver Rama desde Programa
                            nombre_rama_final = ''
                            try:
                                prog_id = reg.get('programa')
                                if prog_id and str(prog_id).isdigit():
                                    prog_obj = programas_dict.get(int(prog_id))
                                else:
                                    prog_obj = next((p for p in programas_dict.values() if p.Nombre_Programa.strip().lower() == nombre_programa.strip().lower()), None)
                                if prog_obj:
                                    nombre_rama_final = ramas_dict.get(prog_obj.Id_Rama_Programa, '')
                            except Exception:
                                pass
                            
                            # Convertir sexo_label a mayúsculas primeras letras
                            sexo_final = 'Hombre' if sexo_label.lower() in ['hombre', 'hombres', 'h'] else 'Mujer'
                            
                            if idx < 3:
                                print(
                                    f"   ✅ Creando fila: Turno={turno_nombre}({turno_id}) "
                                    f"Sexo={sexo_final} Cantidad={cantidad}"
                                )
                            
                            objetos_a_guardar.append(Temp_Egresados(
                                Periodo=periodo_texto_temp,
                                Sigla=unidad_obj.Sigla,
                                Nombre_Programa=nombre_programa,
                                Nombre_Rama=nombre_rama_final,
                                Nivel=nivel_sp,
                                Modalidad=modalidad,
                                Grupo_Edad=grupo_edad,
                                Boleta=boleta,
                                Generacion=generacion,
                                Turno=turno_nombre,
                                Sexo=sexo_final,
                                Id_Semaforo=0,  # Frontend siempre comienza con semáforo = 0 (o Pendiente)
                                Egresados=cantidad
                            ))
                
                else:
                    # ========================
                    # FORMATO SP (Directo)
                    # ========================
                    print(f"\n📊 SP FORMAT detectado en registro[{idx}]")
                    
                    # COPIAR DIRECTAMENTE CAMPOS TEXTUALES DEL SP
                    nombre_programa = str(reg.get('Nombre_Programa') or '')
                    nombre_rama = str(reg.get('Nombre_Rama') or '')
                    nivel_sp = str(reg.get('Nivel') or '')
                    modalidad = str(reg.get('Modalidad') or '')
                    grupo_edad = str(reg.get('Grupo_Edad') or reg.get('Edad') or '')
                    boleta = str(reg.get('Boleta') or '')
                    generacion = str(reg.get('Generacion') or '')
                    turno = str(reg.get('Turno') or '')
                    
                    # Sexo y cantidad
                    sexo_raw = str(reg.get('Sexo') or '').strip().lower()
                    sexo = 'Hombre' if 'h' in sexo_raw or 'hom' in sexo_raw else 'Mujer'
                    
                    # Cantidad: puede venir como Egresados
                    cantidad = reg.get('Egresados')
                    try:
                        cantidad = int(float(cantidad)) if cantidad not in (None, '') else 0
                    except Exception:
                        cantidad = 0
                    
                    # Id_Semaforo (número)
                    id_semaforo = _safe_int(reg.get('Id_Semaforo'), 0)
                    
                    if idx < 3:
                        print(f"   ✅ Mapeando como SP puro (todos campos de texto)")
                    
                    objetos_a_guardar.append(Temp_Egresados(
                        Periodo=periodo_texto_temp,
                        Sigla=unidad_obj.Sigla,
                        Nombre_Programa=nombre_programa,
                        Nombre_Rama=nombre_rama,
                        Nivel=nivel_sp,
                        Modalidad=modalidad,
                        Grupo_Edad=grupo_edad,
                        Boleta=boleta,
                        Generacion=generacion,
                        Turno=turno,
                        Sexo=sexo,
                        Id_Semaforo=id_semaforo,
                        Egresados=cantidad
                    ))
                
            except Exception as e_map:
                print(f"⚠️ Error procesando fila[{idx}]: {str(e_map)}")
                import traceback
                traceback.print_exc()

        print(f"📦 Objetos normalizados para Temp_Egresados: {len(objetos_a_guardar)}")
        for i, obj in enumerate(objetos_a_guardar[:10]):
            print(
                f"📝 TempPreview[{i}] Periodo='{obj.Periodo}' Sigla='{obj.Sigla}' Programa='{obj.Nombre_Programa}' "
                f"Rama='{obj.Nombre_Rama}' Nivel='{obj.Nivel}' Modalidad='{obj.Modalidad}' Boleta='{obj.Boleta}' "
                f"Generacion='{obj.Generacion}' Turno='{obj.Turno}' Sexo='{obj.Sexo}' Semaforo='{obj.Id_Semaforo}' Egresados='{obj.Egresados}'"
            )

        # 5. GUARDADO MASIVO (Instantáneo)
        if objetos_a_guardar:
            db.add_all(objetos_a_guardar)
            db.commit()
            invalidate_egresados_sp_cache(unidad_obj.Sigla, periodo_texto_temp, None)

        count_temp_post = db.query(Temp_Egresados).filter(
            Temp_Egresados.Sigla == unidad_obj.Sigla,
            Temp_Egresados.Periodo == periodo_texto_temp
        ).count()
        print(f"✅ Filas en Temp_Egresados después de guardar: {count_temp_post}")

        return {"success": True, "guardados": len(objetos_a_guardar), "verificacion_temp": count_temp_post}

    except Exception as e:
        db.rollback()
        print(f"❌ Error optimizado: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post('/validar')
async def validar_egresados(request: Request, sess=Depends(get_current_session), db: Session = Depends(get_db)):
    """
    Valida los datos de egresados.
    Ejecuta el SP [dbo].[SP_Valida_Egresados] (Formato 3) para avanzar semáforo y registrar en Validacion.
    """
    try:
        data = await request.json()

        periodo_in = data.get('periodo')
        nota_in = (data.get('nota') or '').strip()
        nivel_in = (data.get('nivel') or '').strip()    # Nivel que el validador está viendo en pantalla
        unidad_in = (data.get('unidad') or '').strip()  # UA que el validador está viendo en pantalla

        # Sesión
        id_rol = int(sess.id_rol)
        usuario_sp = sess.usuario or 'sistema'  # LOGIN
        host_sp = get_request_host(request)

        # Roles permitidos
        if id_rol not in [4, 5, 6, 7, 8, 9]:
            return {"success": False, "message": "Solo roles de validación pueden ejecutar esta acción."}

        # Resolver periodo a literal (si llega como ID)
        if periodo_in is None:
            return {"success": False, "message": "No se recibió el periodo."}

        if str(periodo_in).isdigit():
            per = db.query(Periodo).filter(Periodo.Id_Periodo == int(periodo_in)).first()
            periodo_literal = per.Periodo if per else str(periodo_in)
        else:
            periodo_literal = str(periodo_in)

        # STRATEGY FALLBACK: priorizar lo que viene del body (el nivel/UA que se está viendo)
        # Roles 6-9 no tienen nivel en sesión, así que hay que tomarlo del body
        unidad_sigla = (unidad_in or (sess.sigla_unidad_academica or '').strip())
        if not unidad_sigla:
            try:
                ua = db.query(Unidad_Academica).filter(Unidad_Academica.Id_Unidad_Academica == int(sess.id_unidad_academica)).first()
                unidad_sigla = ua.Sigla if ua else ''
            except Exception:
                unidad_sigla = ''

        if not unidad_sigla:
            return {"success": False, "message": "No se pudo resolver la Unidad Académica."}

        nivel_literal = (nivel_in or (sess.nombre_nivel or '').strip())
        if not nivel_literal and hasattr(sess, 'id_nivel'):
            nivel_literal = str(sess.id_nivel)

        nota_sp = nota_in or f"Validado por {sess.nombre_completo}"

        # Para logging: leer semáforo actual si existe
        try:
            periodo_id_db = db.query(Periodo.Id_Periodo).filter(Periodo.Periodo == periodo_literal).scalar()
            sem = db.query(SemaforoUnidadAcademica).filter(
                SemaforoUnidadAcademica.Id_Periodo == periodo_id_db,
                SemaforoUnidadAcademica.Id_Unidad_Academica == int(sess.id_unidad_academica),
                SemaforoUnidadAcademica.Id_Formato == 3,
            ).first()
            sem_actual = sem.Id_Semaforo if sem else None
        except Exception:
            sem_actual = None

        print(f"\n{'='*60}")
        print("✅ VALIDAR EGRESADOS (SP_Valida_Egresados)")
        print(f"Usuario: {usuario_sp} | Rol: {id_rol}")
        print(f"Periodo: {periodo_literal} | UA: {unidad_sigla} | Nivel: {nivel_literal}")
        print(f"Semáforo actual (si aplica): {sem_actual}")
        print(f"Host: {host_sp}")
        print(f"{'='*60}\n")

        sql = text("""
            SET NOCOUNT ON;
            EXEC [dbo].[SP_Valida_Egresados]
                @PPeriodo = :periodo,
                @UUnidad_Academica = :ua,
                @NNivel = :nivel,
                @uusuario = :usuario,
                @HHost = :host,
                @NNota = :nota
        """)

        result = db.execute(sql, {
            'periodo': periodo_literal,
            'ua': unidad_sigla,
            'nivel': nivel_literal,
            'usuario': usuario_sp,
            'host': host_sp,
            'nota': nota_sp,
        })

        try:
            sp_rows = [dict(r) for r in result.mappings().all()]
        except Exception:
            sp_rows = []

        db.commit()
        invalidate_egresados_sp_cache()

        # Enviar correo de acuse cuando el Titular (id_rol=5) valida Y todos los módulos de la UA ya están en semáforo >= 5
        acuse_info = None
        correo_acuse_enviado = False
        acuse_error = None
        correo_acuse_error = None

        if id_rol == 5:
            ua_obj = db.query(Unidad_Academica).filter(
                Unidad_Academica.Id_Unidad_Academica == int(sess.id_unidad_academica)
            ).first()
            id_ua = int(sess.id_unidad_academica)
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

                    acuse_info, correo_acuse_enviado, acuse_error, correo_acuse_error = enviar_correo_acuse_titular(
                        db=db,
                        id_usuario=int(sess.id_usuario),
                        usuario_login=usuario_sp,
                        nombre_completo=str(sess.nombre_completo or usuario_sp),
                        unidad_sigla=unidad_sigla,
                        unidad_nombre=str(getattr(ua_obj, 'Nombre', '') or unidad_sigla),
                        clave_ur=str(getattr(ua_obj, 'Clave', '') or ''),
                        periodo_literal=periodo_literal,
                        estatus_entrega=estatus_entrega,
                    )
                except Exception as _e:
                    acuse_error = str(_e)
                    print(f"❌ Error inesperado al generar acuse egresados: {_e}")
            else:
                print(f"ℹ️ Egresados validados por Titular. Aún no se genera acuse porque faltan módulos por validar en la UA ({unidad_sigla}).")

        return {
            "success": True,
            "message": "Egresados validados correctamente",
            "correo_acuse_enviado": correo_acuse_enviado,
            "acuse": acuse_info,
            "acuse_error": acuse_error,
            "correo_acuse_error": correo_acuse_error,
        }

    except Exception as e:
        db.rollback()
        print(f"❌ Error al validar egresados: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/rechazar')
async def rechazar_egresados(request: Request, sess=Depends(get_current_session), db: Session = Depends(get_db)):
    """
    Rechaza los datos de egresados.
    Ejecuta el SP [dbo].[SP_Rechaza_Egresados] (Formato 3) para regresar semáforo y registrar en Validacion.
    """
    try:
        data = await request.json()

        periodo_in = data.get('periodo')
        motivo = (data.get('motivo') or '').strip()
        nivel_in = (data.get('nivel') or '').strip()    # Nivel que el validador está viendo en pantalla
        unidad_in = (data.get('unidad') or '').strip()  # UA que el validador está viendo en pantalla

        if not motivo:
            raise HTTPException(status_code=400, detail="Debe proporcionar un motivo de rechazo")

        # Respetar nvarchar(250)
        if len(motivo) > 250:
            motivo = motivo[:250]

        # Sesión
        id_rol = int(sess.id_rol)
        usuario_sp = sess.usuario or 'sistema'
        host_sp = get_request_host(request)

        if id_rol not in [4, 5, 6, 7, 8, 9]:
            return {"success": False, "message": "Solo roles de validación pueden ejecutar esta acción."}

        if periodo_in is None:
            return {"success": False, "message": "No se recibió el periodo."}

        if str(periodo_in).isdigit():
            per = db.query(Periodo).filter(Periodo.Id_Periodo == int(periodo_in)).first()
            periodo_literal = per.Periodo if per else str(periodo_in)
        else:
            periodo_literal = str(periodo_in)

        # STRATEGY FALLBACK: priorizar lo que viene del body (el nivel/UA que se está viendo)
        # Roles 6-9 no tienen nivel en sesión, así que hay que tomarlo del body
        unidad_sigla = (unidad_in or (sess.sigla_unidad_academica or '').strip())
        if not unidad_sigla:
            try:
                ua = db.query(Unidad_Academica).filter(Unidad_Academica.Id_Unidad_Academica == int(sess.id_unidad_academica)).first()
                unidad_sigla = ua.Sigla if ua else ''
            except Exception:
                unidad_sigla = ''

        if not unidad_sigla:
            return {"success": False, "message": "No se pudo resolver la Unidad Académica."}

        nivel_literal = (nivel_in or (sess.nombre_nivel or '').strip())
        if not nivel_literal and hasattr(sess, 'id_nivel'):
            nivel_literal = str(sess.id_nivel)

        print(f"\n{'='*60}")
        print("🔴 RECHAZAR EGRESADOS (SP_Rechaza_Egresados)")
        print(f"Usuario: {usuario_sp} | Rol: {id_rol}")
        print(f"Periodo: {periodo_literal} | UA: {unidad_sigla} | Nivel: {nivel_literal}")
        print(f"Host: {host_sp}")
        print(f"Motivo: {motivo}")
        print(f"{'='*60}\n")

        sql = text("""
            SET NOCOUNT ON;
            EXEC [dbo].[SP_Rechaza_Egresados]
                @PPeriodo = :periodo,
                @UUnidad_Academica = :ua,
                @NNivel = :nivel,
                @UUsuario = :usuario,
                @HHost = :host,
                @NNota = :nota
        """)

        db.execute(sql, {
            'periodo': periodo_literal,
            'ua': unidad_sigla,
            'nivel': nivel_literal,
            'usuario': usuario_sp,
            'host': host_sp,
            'nota': motivo,
        })

        db.commit()
        invalidate_egresados_sp_cache()

        # Notificar por correo (capturista de la misma UA + módulo Egresados + nivel rechazado)
        try:
            correos = obtener_correos_involucrados(
                db=db,
                id_unidad=None,
                id_formato=3,
                id_nivel=nivel_literal,
                unidad_sigla=unidad_sigla,
            )
            print(f"📧 Correos obtenidos para notificación (Egresados): {correos}")
            notificar_rechazo_global(
                modulo_rechazado="Egresados",
                id_rol_que_rechaza=id_rol,
                correos=correos,
                unidad_academica=unidad_sigla,
            )
        except Exception as e_correo:
            # El rechazo ya quedó registrado; un fallo de correo no debe revertirlo.
            print(f"❌ No se pudo notificar el rechazo de Egresados: {e_correo}")

        return {"success": True, "message": "Egresados rechazados. Se notificará al capturista."}
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error al rechazar egresados: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/guardar_avance")
async def guardar_avance_egresados(request: Request, sess=Depends(get_current_session), db: Session = Depends(get_db)):
    """
    Endpoint para Guardar Avance de Egresados.
    Ejecuta el SP SP_Actualiza_Egresados_Por_Unidad_Academica para actualizar 
    la tabla Egresados con los datos de Temp_Egresados y actualizar el semáforo a estado 2 (En Proceso).
    """
    verificar_permiso_formato(db, usuario_id=int(sess.id_usuario), formato_id=3, id_rol=int(sess.id_rol))
    try:
        # Obtener datos del usuario desde cookies
        nombre_usuario = sess.nombre_usuario
        apellidoP_usuario = sess.apellidoP_usuario
        apellidoM_usuario = sess.apellidoM_usuario
        nombre_completo = " ".join(filter(None, [nombre_usuario, apellidoP_usuario, apellidoM_usuario]))
        
        # Obtener unidad académica desde cookies
        unidad_sigla = request.cookies.get("unidad_sigla", "")
        if not unidad_sigla:
            id_unidad_cookie = int(sess.id_unidad_academica)
            if id_unidad_cookie:
                unidad_obj = db.query(Unidad_Academica).filter(
                    Unidad_Academica.Id_Unidad_Academica == id_unidad_cookie
                ).first()
                if unidad_obj and unidad_obj.Sigla:
                    unidad_sigla = unidad_obj.Sigla
        
        # Obtener usuario y host
        usuario_sp = str(getattr(sess, 'usuario', '') or '').strip() or nombre_completo or 'sistema'
        host_sp = get_request_host(request)
        
        # Obtener período desde el request
        data = await request.json()
        periodo_input = data.get('periodo')
        
        # Convertir a formato literal para buscar en Temp_Egresados
        # IMPORTANTE: Buscamos con el periodo ANTERIOR porque /guardar guardó con Id_Periodo - 1
        
        if periodo_input:
            if str(periodo_input).isdigit():
                periodo_obj = db.query(Periodo).filter(Periodo.Id_Periodo == int(periodo_input)).first()
                if periodo_obj:
                    # Para buscar en Temp_Egresados: usar periodo anterior
                    periodo_anterior_id = periodo_obj.Id_Periodo
                    periodo_anterior_obj = db.query(Periodo).filter(Periodo.Id_Periodo == periodo_anterior_id).first()
                    periodo_busqueda = periodo_anterior_obj.Periodo if periodo_anterior_obj else None
                    
                    # Para pasar al SP: usar periodo ACTUAL (el SP hará la conversión internamente)
                    periodo_sp = periodo_obj.Periodo
                    
                    print(f"🔄 Periodo para buscar en Temp: '{periodo_busqueda}' (ID {periodo_anterior_id})")
                    print(f"🔄 Periodo para pasar al SP: '{periodo_sp}' (ID {periodo_input})")
                else:
                    _, periodo_sp = get_ultimo_periodo(db)
                    periodo_busqueda = periodo_sp
            else:
                periodo_sp = str(periodo_input)
                periodo_busqueda = periodo_sp
        else:
            # Obtener periodo actual y calcular periodo anterior para buscar en Temp_Egresados
            periodo_actual_id, periodo_actual_literal = get_ultimo_periodo(db)
            periodo_sp = periodo_actual_literal
            periodo_busqueda = periodo_sp
            try:
                periodo_anterior_id = int(periodo_actual_id) - 1 if periodo_actual_id else None
                if periodo_anterior_id:
                    periodo_anterior_obj = db.query(Periodo).filter(Periodo.Id_Periodo == periodo_anterior_id).first()
                    if periodo_anterior_obj:
                        periodo_busqueda = periodo_anterior_obj.Periodo
                        print(f"🔄 Período por defecto (anterior) para Temp: '{periodo_busqueda}' (ID {periodo_anterior_id})")
            except Exception:
                # Si algo falla, usar el literal del periodo actual como búsqueda (fallback)
                periodo_busqueda = periodo_sp
        
        # Obtener nivel
        nivel = sess.nombre_nivel
        
        if not all([unidad_sigla, periodo_sp, nivel]):
            return {
                "error": "Faltan parámetros obligatorios",
                "detalles": {
                    "unidad_sigla": unidad_sigla,
                    "periodo": periodo_sp,
                    "nivel": nivel
                }
            }
        
        print(f"\n{'='*60}")
        print(f"GUARDANDO AVANCE DE EGRESADOS")
        print(f"Usuario: {usuario_sp}")
        print(f"Unidad Académica: {unidad_sigla}")
        print(f"Período para SP: {periodo_sp}")
        print(f"Período para buscar: {periodo_busqueda}")
        print(f"Nivel: {nivel}")
        print(f"Host: {host_sp}")
        print(f"{'='*60}")
        
        # Añadir este debug antes del EXEC en guardar_avance_egresados
        count_check = db.query(Temp_Egresados).filter(
            Temp_Egresados.Sigla == unidad_sigla,
            Temp_Egresados.Periodo == periodo_sp
        ).count()
        print(f"DEBUG: Filas encontradas en Temp_Egresados antes del SP: {count_check}")

        # Ejecutar el stored procedure con el periodo ACTUAL (el SP hará la conversión)
        sql = text("""
            EXEC [dbo].[SP_Actualiza_Egresados_Por_Unidad_Academica]
                @UUnidad_Academica = :unidad,
                @UUsuario = :usuario,
                @PPeriodo = :periodo,
                @HHost = :host,
                @NNivel = :nivel
        """)

        result = db.execute(sql, {
            'unidad': unidad_sigla,
            'usuario': usuario_sp,
            'periodo': periodo_sp,  # Pasar periodo ACTUAL al SP
            'host': host_sp,
            'nivel': nivel
        })
        
        db.commit()
        invalidate_egresados_sp_cache(unidad_sigla, periodo_sp, nivel)
        
        print(f"✅ SP ejecutado exitosamente - Avance guardado")
        
        return {
            "success": True,
            "mensaje": "Avance guardado exitosamente. Los datos han sido actualizados en la tabla Egresados.",
            "semaforo_actualizado": "En Proceso (ID=2)"
        }
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error al guardar avance: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": f"Error al guardar el avance: {str(e)}"}


@router.post("/finalizar_captura")
async def finalizar_captura_egresados(request: Request, sess=Depends(get_current_session), db: Session = Depends(get_db)):
    """
    Endpoint para Finalizar Captura de Egresados.
    Ejecuta el SP SP_Actualiza_Egresados_Por_Semestre_AU que:
    1. Actualiza el semáforo del semestre específico a estado 3 (Completado)
    2. Llama internamente a SP_Actualiza_Egresados_Por_Unidad_Academica
    3. Devuelve la consulta actualizada de egresados
    """
    verificar_permiso_formato(db, usuario_id=int(sess.id_usuario), formato_id=3, id_rol=int(sess.id_rol))
    try:
        # Obtener datos del usuario desde cookies
        nombre_usuario = sess.nombre_usuario
        apellidoP_usuario = sess.apellidoP_usuario
        apellidoM_usuario = sess.apellidoM_usuario
        nombre_completo = " ".join(filter(None, [nombre_usuario, apellidoP_usuario, apellidoM_usuario]))
        
        # Obtener unidad académica desde cookies
        unidad_sigla = request.cookies.get("unidad_sigla", "")
        if not unidad_sigla:
            id_unidad_cookie = int(sess.id_unidad_academica)
            if id_unidad_cookie:
                unidad_obj = db.query(Unidad_Academica).filter(
                    Unidad_Academica.Id_Unidad_Academica == id_unidad_cookie
                ).first()
                if unidad_obj and unidad_obj.Sigla:
                    unidad_sigla = unidad_obj.Sigla
        
        # Obtener usuario y host
        usuario_sp = str(getattr(sess, 'usuario', '') or '').strip() or nombre_completo or 'sistema'
        host_sp = get_request_host(request)
        
        # Obtener parámetros desde el request
        data = await request.json()
        periodo_input = data.get('periodo')
        programa_id = data.get('programa')
        modalidad_id = data.get('modalidad')
        
        # Convertir período a formato literal
        if periodo_input:
            if str(periodo_input).isdigit():
                periodo_obj = db.query(Periodo).filter(Periodo.Id_Periodo == int(periodo_input)).first()
                if periodo_obj:
                    periodo = periodo_obj.Periodo
                else:
                    _, periodo = get_ultimo_periodo(db)
            else:
                periodo = str(periodo_input)
        else:
            _, periodo = get_ultimo_periodo(db)
        
        # Obtener nivel
        nivel = sess.nombre_nivel
        
        # Obtener nombres literales de programa y modalidad
        programa_obj = db.query(Programas).filter(Programas.Id_Programa == int(programa_id)).first()
        programa_nombre = programa_obj.Nombre_Programa if programa_obj else ''
        
        modalidad_obj = db.query(Modalidad).filter(Modalidad.Id_Modalidad == int(modalidad_id)).first()
        modalidad_nombre = modalidad_obj.Modalidad if modalidad_obj else ''
        
        if not all([unidad_sigla, programa_nombre, modalidad_nombre, periodo, nivel]):
            return {
                "error": "Faltan parámetros obligatorios",
                "detalles": {
                    "unidad_sigla": unidad_sigla,
                    "programa": programa_nombre,
                    "modalidad": modalidad_nombre,
                    "periodo": periodo,
                    "nivel": nivel
                }
            }
        
        print(f"\n{'='*60}")
        print(f"FINALIZANDO CAPTURA DE EGRESADOS")
        print(f"Usuario: {usuario_sp}")
        print(f"Unidad Académica: {unidad_sigla}")
        print(f"Programa: {programa_nombre}")
        print(f"Modalidad: {modalidad_nombre}")
        print(f"Período: {periodo}")
        print(f"Nivel: {nivel}")
        print(f"Host: {host_sp}")
        print(f"{'='*60}")
        
        # Determinar periodo de búsqueda en Temp_Egresados (usualmente el periodo anterior)
        periodo_busqueda = periodo
        try:
            # Intentar obtener Id del periodo literal actual y buscar el anterior
            periodo_obj = db.query(Periodo).filter(Periodo.Periodo == periodo).first()
            if periodo_obj and periodo_obj.Id_Periodo:
                periodo_anterior_id = int(periodo_obj.Id_Periodo) - 1
                periodo_anterior_obj = db.query(Periodo).filter(Periodo.Id_Periodo == periodo_anterior_id).first()
                if periodo_anterior_obj:
                    periodo_busqueda = periodo_anterior_obj.Periodo
                    print(f"🔄 Periodo para buscar en Temp (anterior): '{periodo_busqueda}' (ID {periodo_anterior_id})")
        except Exception:
            periodo_busqueda = periodo

        def _texto(valor):
            return str(valor or '').strip()

        def _entero(valor, default=0):
            try:
                if valor is None:
                    return default
                texto = str(valor).strip()
                if texto == '':
                    return default
                return int(float(texto))
            except Exception:
                return default

        def _leer_valor(registro, campo, default=None):
            if isinstance(registro, dict):
                return registro.get(campo, default)
            return getattr(registro, campo, default)

        def _clave_temp(registro):
            return (
                _texto(_leer_valor(registro, 'Nombre_Programa')),
                _texto(_leer_valor(registro, 'Nombre_Rama')),
                _texto(_leer_valor(registro, 'Nivel')),
                _texto(_leer_valor(registro, 'Modalidad')),
                _texto(_leer_valor(registro, 'Grupo_Edad') or _leer_valor(registro, 'Edad')),
                _texto(_leer_valor(registro, 'Boleta')),
                _texto(_leer_valor(registro, 'Generacion')),
                _texto(_leer_valor(registro, 'Turno')),
                _texto(_leer_valor(registro, 'Sexo')),
            )

        # Sembrar Temp_Egresados si no existe avance previo o si faltan filas para esta captura
        try:
            temp_existente = db.query(Temp_Egresados).filter(
                Temp_Egresados.Sigla == unidad_sigla,
                Temp_Egresados.Periodo == periodo_busqueda,
                Temp_Egresados.Nivel == nivel,
            ).all()

            temp_por_clave = {
                _clave_temp(row): (_entero(row.Egresados, 0) if row.Egresados is not None else 0)
                for row in temp_existente
            }

            if temp_existente:
                print(f"📦 Temp_Egresados existente antes de finalizar: {len(temp_existente)} filas")

            # Obtener todas las filas actuales de consulta para esta UA / período / nivel.
            # El SP final consume Temp_Egresados completa para la unidad, así que no debemos
            # limitar la semilla solo al programa/modalidad seleccionados.
            filas_consulta, _ = execute_egresados_sp(
                db=db,
                unidad_sigla=unidad_sigla,
                periodo_literal=periodo,
                nivel_nombre=nivel,
                usuario=usuario_sp,
                host=host_sp,
            )

            print(f"📊 Filas de consulta totales para semilla Temp_Egresados: {len(filas_consulta)}")

            filas_temp_a_guardar = []
            filas_base = filas_consulta if filas_consulta else temp_existente

            for fila in filas_base:
                clave = _clave_temp(fila)
                egresados_valor = _entero(_leer_valor(fila, 'Egresados'), 0)

                if clave in temp_por_clave:
                    egresados_valor = temp_por_clave[clave]
                elif egresados_valor is None:
                    egresados_valor = 0

                filas_temp_a_guardar.append(Temp_Egresados(
                    Periodo=periodo_busqueda,
                    Sigla=unidad_sigla,
                    Nombre_Programa=_texto(_leer_valor(fila, 'Nombre_Programa')),
                    Nombre_Rama=_texto(_leer_valor(fila, 'Nombre_Rama')),
                    Nivel=_texto(_leer_valor(fila, 'Nivel')),
                    Modalidad=_texto(_leer_valor(fila, 'Modalidad')),
                    Grupo_Edad=_texto(_leer_valor(fila, 'Grupo_Edad') or _leer_valor(fila, 'Edad')),
                    Boleta=_texto(_leer_valor(fila, 'Boleta')),
                    Generacion=_texto(_leer_valor(fila, 'Generacion')),
                    Turno=_texto(_leer_valor(fila, 'Turno')),
                    Sexo=_texto(_leer_valor(fila, 'Sexo')),
                    Id_Semaforo=_entero(_leer_valor(fila, 'Id_Semaforo'), 0),
                    Egresados=egresados_valor,
                ))

            # Si ya existían filas en Temp_Egresados y la consulta no las devolvió por alguna
            # razón, conservarlas para no perder información previa.
            if temp_existente:
                claves_guardadas = {_clave_temp(fila) for fila in filas_base}
                for fila in temp_existente:
                    if _clave_temp(fila) not in claves_guardadas:
                        filas_temp_a_guardar.append(fila)

            if filas_temp_a_guardar:
                db.query(Temp_Egresados).filter(
                    Temp_Egresados.Sigla == unidad_sigla,
                    Temp_Egresados.Periodo == periodo_busqueda,
                    Temp_Egresados.Nivel == nivel,
                ).delete(synchronize_session=False)
                db.add_all(filas_temp_a_guardar)
                db.commit()
                print(f"✅ Temp_Egresados preparado para finalización: {len(filas_temp_a_guardar)} filas")
            else:
                print("⚠️ No se encontraron filas para sembrar Temp_Egresados antes de finalizar")
        except Exception as e_temp:
            db.rollback()
            print(f"⚠️ No se pudo preparar Temp_Egresados para finalización: {str(e_temp)}")
            import traceback
            traceback.print_exc()

        # Ejecutar el stored procedure y obtener resultados (el SP devuelve la consulta actualizada)
        # Log payload para depuración
        try:
            raw_payload = await request.json()
        except Exception:
            raw_payload = None
        print(f"🔔 Payload recibido en finalizar_captura: {raw_payload}")
        sql = text("""
            EXEC [dbo].[SP_Actualiza_Egresados_Por_Semestre_AU]
                @UUnidad_Academica = :unidad,
                @PPrograma = :programa,
                @MModalidad = :modalidad,
                @UUsuario = :usuario,
                @PPeriodo = :periodo,
                @HHost = :host,
                @NNivel = :nivel
        """)

        rows_list = []
        sp_error = False
        sp_error_msg = ''
        try:
            result = db.execute(sql, {
                'unidad': unidad_sigla,
                'programa': programa_nombre,
                'modalidad': modalidad_nombre,
                'usuario': usuario_sp,
                'periodo': periodo,
                'host': host_sp,
                'nivel': nivel
            })

            # SQLAlchemy Result may not return rows for non-SELECT SPs
            if getattr(result, 'returns_rows', False):
                try:
                    rows = result.fetchall()
                    cols = result.keys()
                    for r in rows:
                        try:
                            # row may be RowMapping or tuple
                            if hasattr(r, '_mapping'):
                                rows_list.append(dict(r._mapping))
                            else:
                                rows_list.append(dict(zip(cols, r)))
                        except Exception:
                            try:
                                rows_list.append(dict(r))
                            except Exception:
                                pass
                except Exception as e_fetch:
                    print(f"⚠️ Error al leer filas del resultado SP: {str(e_fetch)}")
            else:
                # No devuelve filas (ej. SP que realiza UPDATE/INSERT)
                print("ℹ️ El SP no devolvió filas; asumido como operación de actualización.")

            try:
                result.close()
            except Exception:
                pass

            db.commit()
            invalidate_egresados_sp_cache(unidad_sigla, periodo, nivel)

            # =========================================================================
            # NUEVA LÓGICA AUTOMÁTICA CORREGIDA: Periodo Activo ID - 1 (Egresados)
            # =========================================================================
            try:
                # 1. Obtener el Periodo Activo de la base de datos
                # Usamos la variable local 'periodo' que definiste arriba en tu endpoint
                periodo_activo = db.query(Periodo).filter(Periodo.Periodo == periodo).first()

                if periodo_activo:
                    # 2. Aplicar la regla matemática (-1 al ID del activo: Ej. 20 - 1 = 19)
                    id_periodo_check = periodo_activo.Id_Periodo - 1

                    # 3. Obtener el objeto del Periodo Anterior para extraer su texto/nombre (Ej: "2024-2025/1")
                    periodo_anterior_obj = db.query(Periodo).filter(Periodo.Id_Periodo == id_periodo_check).first()
                    p_anterior_str = periodo_anterior_obj.Periodo if periodo_anterior_obj else str(periodo_busqueda)

                    # 4. Obtener el ID numérico de la Unidad Académica que se está procesando
                    unidad_db = db.query(Unidad_Academica).filter(Unidad_Academica.Sigla == unidad_sigla).first()
                    id_unidad_check = unidad_db.Id_Unidad_Academica if unidad_db else None

                    id_nivel_cookie = getattr(sess, 'id_nivel', None)
                    id_nivel_check = 0 if id_nivel_cookie in ("None", None, "") else int(id_nivel_cookie)

                    if id_unidad_check and id_nivel_check:
                        # 5. Contar cuántos semáforos NO están en 3 para el Id_Periodo exacto (19)
                        pendientes = db.query(SemaforoSemestreUnidadAcademica).filter(
                            SemaforoSemestreUnidadAcademica.Id_Periodo == id_periodo_check,
                            SemaforoSemestreUnidadAcademica.Id_Unidad_Academica == id_unidad_check,
                            SemaforoSemestreUnidadAcademica.Id_Nivel == id_nivel_check,
                            SemaforoSemestreUnidadAcademica.Id_Formato == 3,
                            SemaforoSemestreUnidadAcademica.Id_Semaforo != 3
                        ).count()

                        # Contar el total de semáforos existentes para ese periodo anterior
                        total_registros = db.query(SemaforoSemestreUnidadAcademica).filter(
                            SemaforoSemestreUnidadAcademica.Id_Periodo == id_periodo_check,
                            SemaforoSemestreUnidadAcademica.Id_Unidad_Academica == id_unidad_check,
                            SemaforoSemestreUnidadAcademica.Id_Nivel == id_nivel_check,
                            SemaforoSemestreUnidadAcademica.Id_Formato == 3
                        ).count()

                        print(f"🔍 [Egresados] Periodo Activo ID: {periodo_activo.Id_Periodo} | Evaluando Periodo Egresados ID: {id_periodo_check}")
                        print(f"🔍 [Egresados] Semáforos Formato 3: {total_registros} totales, {pendientes} pendientes por finalizar")

                        # 6. Disparar el SP de cierre solo si existen registros y TODOS están en estado 3
                        if total_registros > 0 and pendientes == 0:
                            print(f"🎉 ¡Todos los semáforos del periodo ID {id_periodo_check} ({p_anterior_str}) están en 3! Ejecutando SP_Finaliza_Captura_Egresados...")
                            
                            sql_finaliza = text("""
                                EXEC [dbo].[SP_Finaliza_Captura_Egresados]
                                    @PPeriodo = :periodo,
                                    @UUnidad_Academica = :unidad,
                                    @MModalidad = :modalidad,
                                    @PPrograma = :programa,
                                    @UUsuario = :usuario,
                                    @HHost = :host,
                                    @NNivel = :nivel
                            """)
                            
                            db.execute(sql_finaliza, {
                                'periodo': p_anterior_str,
                                'unidad': unidad_sigla,
                                'modalidad': modalidad_nombre,
                                'programa': programa_nombre,
                                'usuario': usuario_sp,
                                'host': host_sp,
                                'nivel': nivel
                            })
                            db.commit()
                            print(f"✅ SP_Finaliza_Captura_Egresados ejecutado exitosamente para '{p_anterior_str}' (ID: {id_periodo_check})")
            except Exception as e_check:
                print(f"⚠️ Error en la automatización del SP final o validación de semáforos: {str(e_check)}")
            # =========================================================================

        except Exception as e_exec:
            db.rollback()
            sp_error = True
            sp_error_msg = str(e_exec)
            print(f"⚠️ Error ejecutando SP de finalización: {sp_error_msg}")
            import traceback
            traceback.print_exc()

        if sp_error:
            return {
                "success": False,
                "error": "Error ejecutando SP de finalización",
                "details": sp_error_msg
            }

        print(f"✅ SP ejecutado exitosamente - Captura finalizada")
        print(f"📋 Registros devueltos: {len(rows_list)}")

        return {
            "success": True,
            "mensaje": f"Captura de {programa_nombre} ({modalidad_nombre}) finalizada exitosamente.",
            "semaforo_actualizado": "Completado (ID=3)",
            "datos_actualizados": rows_list
        }
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error al finalizar captura: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": f"Error al finalizar la captura: {str(e)}"}

@router.get('/informe')
async def obtener_informe_egresados(request: Request, sess=Depends(validar_acuse), db: Session = Depends(get_db)):
    """
    Obtiene el informe de egresados desde el SP para mostrar en la tabla de informe.
    Devuelve los datos reales guardados en la base de datos.
    """
    try:
        # Obtener datos del usuario desde cookies
        id_unidad_academica = int(sess.id_unidad_academica)
        id_nivel_cookie = sess.id_nivel
        
        if id_nivel_cookie == "None" or id_nivel_cookie is None or id_nivel_cookie == "":
            id_nivel = 0
        else:
            id_nivel = int(id_nivel_cookie)
        
        nombre_usuario = sess.nombre_usuario
        apellidoP_usuario = sess.apellidoP_usuario
        apellidoM_usuario = sess.apellidoM_usuario
        nombre_completo = " ".join(filter(None, [nombre_usuario, apellidoP_usuario, apellidoM_usuario]))
        
        print(f"\n{'='*60}")
        print(f"OBTENIENDO INFORME DE EGRESADOS")
        print(f"Usuario: {nombre_completo}")
        print(f"ID Unidad Académica: {id_unidad_academica}")
        print(f"ID Nivel: {id_nivel}")
        print(f"{'='*60}")
        
        # Obtener periodo activo
        periodo_id, periodo_literal = get_ultimo_periodo(db)
        if not periodo_id or not periodo_literal:
            return {"success": False, "error": "No hay un periodo activo configurado"}

        #Obetener periodo anterior al activo
        periodo_anterior_id = int(periodo_id) - 1
        periodo_anterior = db.query(Periodo).filter(Periodo.Id_Periodo == periodo_anterior_id).first()
        periodo_anterior_literal = periodo_anterior.Periodo if periodo_anterior else None
        
        # Obtener información de unidad y nivel
        unidad_actual = db.query(Unidad_Academica).filter(
            Unidad_Academica.Id_Unidad_Academica == id_unidad_academica
        ).first()
        
        if not unidad_actual:
            return {"success": False, "error": "No se pudo identificar la unidad académica"}
        
        nivel = db.query(Nivel).filter(Nivel.Id_Nivel == id_nivel).first()
        nivel_nombre = nivel.Nivel if nivel else ""
        
        # Ejecutar SP para obtener datos
        egresados_data, _ = execute_egresados_sp(
            db=db,
            unidad_sigla=unidad_actual.Sigla,
            periodo_literal=periodo_literal,
            nivel_nombre=nivel_nombre,
            usuario=nombre_completo,
            host=get_request_host(request)
        )
        
        print(f"📊 Datos obtenidos del SP: {len(egresados_data)} registros (antes de filtrar)")
        
        # Filtrar solo registros donde Egresados no sea NULL
        egresados_filtrados = []
        for registro in egresados_data:
            egresados = registro.get('Egresados')
            
            # Incluir solo si Egresados no es NULL
            if egresados is not None and egresados >= 0:
                egresados_filtrados.append(registro)
        
        print(f"✅ Datos filtrados: {len(egresados_filtrados)} registros (con egresados != NULL)")
        
        return {
            "success": True,
            "datos": egresados_filtrados,
            "total_registros": len(egresados_filtrados)
        }
        
    except Exception as e:
        print(f"❌ Error al obtener informe: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


@router.post('/estados_semaforo')
async def obtener_estados_semaforo_por_turnos(request: Request, sess=Depends(get_current_session), db: Session = Depends(get_db)):
    """
    Endpoint para obtener los estados de semáforo por turno.
    
    Retorna un diccionario con el formato: { "turnoId": estadoId }
    Ejemplo: { "1": 2, "2": 1, "3": 3 } donde 1=Matutino, 2=Vespertino, 3=Mixto
    
    Estados de semáforo:
    - 1: Rojo (Sin datos o incompleto)
    - 2: Amarillo (En proceso)
    - 3: Verde (Completado)
    """
    try:
        data = await request.json()
        periodo_input = data.get('periodo')
        programa_id = data.get('programa')
        modalidad_id = data.get('modalidad')
        id_unidad_payload = data.get('id_unidad_academica')

        if not programa_id:
            return {"success": False, "error": "No se recibió programa"}

        def _norm(valor: Any) -> str:
            import unicodedata
            txt = str(valor or '').strip().lower()
            txt = unicodedata.normalize('NFD', txt)
            txt = ''.join(ch for ch in txt if unicodedata.category(ch) != 'Mn')
            return txt

        def _resolver_estado_id(row: Dict[str, Any]) -> int:
            for key in ("Id_Semaforo", "id_semaforo", "ID_SEMAFORO"):
                v = row.get(key)
                if v is not None and str(v).strip() != '':
                    try:
                        estado = int(v)
                        if estado in (1, 2, 3):
                            return estado
                    except Exception:
                        pass

            texto_estado = row.get('Estado_Semaforo') or row.get('estado_semaforo') or ''
            txt = _norm(texto_estado)
            if 'final' in txt or 'complet' in txt or 'validad' in txt:
                return 3
            if 'proceso' in txt or 'captura' in txt:
                return 2
            return 1

        # Resolver período literal
        periodo_literal = None
        if periodo_input:
            if str(periodo_input).isdigit():
                per = db.query(Periodo).filter(Periodo.Id_Periodo == int(periodo_input)).first()
                periodo_literal = per.Periodo if per else None
            else:
                periodo_literal = str(periodo_input)
        if not periodo_literal:
            _, periodo_literal = get_ultimo_periodo(db)
        if not periodo_literal:
            return {"success": False, "error": "No se pudo resolver el período"}

        # Resolver UA y nivel para ejecutar el mismo SP de consulta
        id_unidad_academica = id_unidad_payload or getattr(sess, 'id_unidad_academica', None)
        unidad_sigla = ''
        if id_unidad_academica:
            try:
                ua = db.query(Unidad_Academica).filter(
                    Unidad_Academica.Id_Unidad_Academica == int(id_unidad_academica)
                ).first()
                unidad_sigla = ua.Sigla if ua else ''
            except Exception:
                unidad_sigla = ''
        if not unidad_sigla:
            unidad_sigla = str(getattr(sess, 'sigla_unidad_academica', '') or '').strip()
        if not unidad_sigla:
            return {"success": False, "error": "No se pudo resolver la unidad académica"}

        nivel_nombre = str(getattr(sess, 'nombre_nivel', '') or '').strip()
        if not nivel_nombre:
            id_nivel_sess = getattr(sess, 'id_nivel', None)
            try:
                if id_nivel_sess and str(id_nivel_sess).strip() not in ('', 'None'):
                    niv = db.query(Nivel).filter(Nivel.Id_Nivel == int(id_nivel_sess)).first()
                    nivel_nombre = niv.Nivel if niv else ''
            except Exception:
                nivel_nombre = ''
        if not nivel_nombre:
            return {"success": False, "error": "No se pudo resolver el nivel académico"}

        programa = db.query(Programas).filter(Programas.Id_Programa == int(programa_id)).first()
        if not programa:
            return {"success": False, "error": "Programa no válido"}
        programa_nombre = str(programa.Nombre_Programa or '').strip()

        modalidad_nombre = None
        if modalidad_id not in (None, '', 'null', 'None'):
            try:
                modalidad_obj = db.query(Modalidad).filter(Modalidad.Id_Modalidad == int(modalidad_id)).first()
                modalidad_nombre = str(modalidad_obj.Modalidad or '').strip() if modalidad_obj else None
            except Exception:
                modalidad_nombre = None

        usuario_sp = str(getattr(sess, 'usuario', '') or 'sistema')
        host_sp = get_request_host(request)

        print(f"\n{'='*60}")
        print("OBTENIENDO SEMÁFORO DESDE SP_Consulta_Egresados")
        print(f"Periodo: {periodo_literal}")
        print(f"UA: {unidad_sigla}")
        print(f"Nivel: {nivel_nombre}")
        print(f"Programa ID: {programa_id} | Programa: {programa_nombre}")
        print(f"Modalidad seleccionada: {modalidad_id} | Nombre: {modalidad_nombre}")
        print(f"{'='*60}")

        rows_sp, _ = execute_egresados_sp(
            db=db,
            unidad_sigla=unidad_sigla,
            periodo_literal=periodo_literal,
            nivel_nombre=nivel_nombre,
            usuario=usuario_sp,
            host=host_sp,
        )

        rows_programa = [
            r for r in rows_sp
            if _norm(r.get('Nombre_Programa') or r.get('nombre_programa')) == _norm(programa_nombre)
        ]

        if modalidad_nombre:
            rows_programa = [
                r for r in rows_programa
                if _norm(r.get('Modalidad') or r.get('modalidad')) == _norm(modalidad_nombre)
            ]
        else:
            print("⚠️ No se pudo resolver la modalidad seleccionada; se mantuvo el filtro por programa")

        print(f"📊 Filas SP totales: {len(rows_sp)}")
        print(f"📊 Filas SP del programa '{programa_nombre}' y modalidad '{modalidad_nombre}': {len(rows_programa)}")

        turnos_db = db.query(Turno).filter(Turno.Id_Estatus == 1).all()
        turno_nombre_a_id = {_norm(t.Turno): int(t.Id_Turno) for t in turnos_db}
        estado_por_turno: Dict[str, int] = {str(int(t.Id_Turno)): 1 for t in turnos_db}

        for row in rows_programa:
            turno_id = None
            v_turno_id = row.get('Id_Turno') or row.get('id_turno')
            if v_turno_id is not None and str(v_turno_id).strip() != '':
                try:
                    turno_id = int(v_turno_id)
                except Exception:
                    turno_id = None

            if turno_id is None:
                turno_nombre = _norm(row.get('Turno') or row.get('turno'))
                turno_id = turno_nombre_a_id.get(turno_nombre)

            if not turno_id:
                continue

            estado_id = _resolver_estado_id(row)
            key_turno = str(int(turno_id))
            estado_actual = int(estado_por_turno.get(key_turno, 1))
            estado_por_turno[key_turno] = max(estado_actual, estado_id)

        print(f"✅ Estados de semáforo mapeados desde SP: {estado_por_turno}")

        return {
            "success": True,
            "estados_semaforo": estado_por_turno,
        }
        
    except Exception as e:
        print(f"❌ Error al obtener estados de semáforo: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

validar_acuse = VerificarAccesoAcuse()

@router.get('/resumen-dinamico')
async def resumen_egresados_dinamico_view(
    request: Request, 
    periodo: str = None,
    nivel: str = None,
    unidad: str = None, 
    sess=Depends(validar_acuse),
    db: Session = Depends(get_db),
    vista: str = 'resumen',
    exportando_pdf: bool = False
):
    fecha_hoy = datetime.now().strftime('%d/%m/%Y')

    final_unidad = unidad if (unidad and unidad.strip()) else sess.sigla_unidad_academica
    final_nivel = nivel if (nivel and nivel.strip()) else sess.nombre_nivel

    """
    Vista de resumen dinámico de egresados con estructura adaptativa.
    Muestra por Programa → Modalidad → Boletas → Generaciones → Tipo (Regular/Extemporáneo) → Género (H/M/T).
    """
    # Obtener datos del usuario logueado
    id_rol = int(sess.id_rol)
    nombre_rol = sess.nombre_rol
    nombre_usuario = sess.nombre_usuario
    apellidoP_usuario = sess.apellidoP_usuario
    apellidoM_usuario = sess.apellidoM_usuario
    nombre_completo = " ".join(filter(None, [nombre_usuario, apellidoP_usuario, apellidoM_usuario]))

    # Validar que el usuario tenga rol superior (4-9)
    roles_permitidos = [1, 4, 5, 6, 7, 8, 9]
    if id_rol not in roles_permitidos:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_message": f"Acceso denegado: Su rol ({nombre_rol}) no tiene permisos para acceder a esta funcionalidad.",
            "redirect_url": "/mod_principal/",
            "session": sess
        })

    print(f"\n{'='*60}")
    print(f"RESUMEN DINÁMICO DE EGRESADOS")
    print(f"Periodo: {periodo}, Nivel: {final_nivel}, Unidad: {final_unidad}")
    print(f"Usuario: {nombre_completo} ({nombre_rol})")
    print(f"{'='*60}")

    vista_normalizada = str(vista or '').strip().lower()
    es_vista_acuse = vista_normalizada == 'acuse'
    es_rol_con_acuse = id_rol in [4, 5, 6, 7, 8, 9]
    nombre_template = "egresados_acuse_nuevo.html" if (es_vista_acuse or es_rol_con_acuse) else "egresados_resumen_dinamico.html"  

    try:
        # ------------------------------------------------------------
        # Resolver Id_Periodo (para validación/rechazo desde la vista)
        # ------------------------------------------------------------
        from backend.database.models.CatPeriodo import CatPeriodo

        periodo_obj = db.query(CatPeriodo).filter(CatPeriodo.Periodo == periodo).first()
        periodo_id = int(periodo_obj.Id_Periodo) if periodo_obj else None

        # Obtener datos del SP de egresados
        host = get_request_host(request)
        usuario_login = sess.usuario
        
        egresados_data, nota_rechazo = execute_egresados_sp(
            db=db,
            unidad_sigla=final_unidad,
            periodo_literal=periodo,
            nivel_nombre=final_nivel,
            usuario=nombre_completo,
            host=host
        )

        # ------------------------------------------------------------
        # Estado de validación/rechazo (roles 4-9)
        # ------------------------------------------------------------

        # === RESOLVER UNIDAD Y NIVEL EVALUADOS DESDE LA URL QUERIED ===
        ua_obj = db.query(Unidad_Academica).filter(
            (Unidad_Academica.Sigla == final_unidad) | (Unidad_Academica.Nombre == final_unidad)
        ).first()
        id_ua_evaluar = ua_obj.Id_Unidad_Academica if ua_obj else int(getattr(sess, 'id_unidad_academica', 0) or 0)

        nivel_obj = db.query(Nivel).filter(Nivel.Nivel == final_nivel).first()
        id_nivel_evaluar = nivel_obj.Id_Nivel if nivel_obj else int(getattr(sess, 'id_nivel', 0) or 0)

        # === OBTENER EL PERIODO ANTERIOR (EN EGRESADOS EL SEMÁFORO PERTENECE AL PERIODO ANTERIOR) ===
        periodo_anterior_id, periodo_anterior_literal = get_periodo_anterior_al_ultimo(db)

        puede_validar = False
        usuario_ya_valido = False
        usuario_ya_rechazo = False
        esperando_por_rol = "Capturista"
        estado_semaforo = None

        try:
            if id_rol in [4, 5, 6, 7, 8, 9] and periodo_id is not None:
                semaforo_unidad = db.query(SemaforoUnidadAcademica).filter(
                    SemaforoUnidadAcademica.Id_Periodo == periodo_anterior_id,
                    SemaforoUnidadAcademica.Id_Unidad_Academica == id_ua_evaluar,
                    SemaforoUnidadAcademica.Id_Nivel == id_nivel_evaluar,
                    SemaforoUnidadAcademica.Id_Formato == 3  # Formato 3 = Egresados
                ).first()

                estado_semaforo = semaforo_unidad.Id_Semaforo if semaforo_unidad else None

                # Calcular con quién está la información según el estado del semáforo
                if estado_semaforo is not None and estado_semaforo > 0:
                    if estado_semaforo in [1, 2]:
                        esperando_por_rol = "Capturista"
                    elif estado_semaforo < 9:
                        semaforo_a_siguiente_rol = {
                            3: 4,  # Semáforo 3 -> Sigue CEGET (4)
                            4: 5,  # Semáforo 4 -> Sigue Titular UA (5)
                            5: 6,  # Semáforo 5 -> Sigue Analista (6)
                            6: 7,  # Semáforo 6 -> Sigue Jefe/a de Departamento (7)
                            7: 8,  # Semáforo 7 -> Sigue Jefe/a de División (8)
                            8: 9,  # Semáforo 8 -> Sigue Director/a de DII (9)
                        }
                        try:
                            siguiente_rol_id = semaforo_a_siguiente_rol.get(estado_semaforo, int(estado_semaforo) + 1)
                            rol_obj = db.query(CatRoles).filter(CatRoles.Id_Rol == siguiente_rol_id).first()
                            esperando_por_rol = rol_obj.Rol if rol_obj else "Capturista"
                        except Exception:
                            esperando_por_rol = "Capturista"
                    else:
                        esperando_por_rol = None
                else:
                    esperando_por_rol = "Capturista"

                # Regla de jerarquía real (alineada a los SPs de Validar/Rechazar):
                # SP_Valida_Egresados y SP_Rechaza_Egresados validan que:
                #   sua.Id_Semaforo == (Id_Rol del usuario) - 1
                semaforo_esperado = id_rol - 1

                if estado_semaforo is not None:
                    if estado_semaforo == semaforo_esperado:
                        puede_validar = True
                        usuario_ya_valido = False
                        usuario_ya_rechazo = False
                    elif estado_semaforo > semaforo_esperado:
                        usuario_ya_valido = True
                    else:
                        # Aún no toca este nivel
                        puede_validar = False

                # Si ya rechazó, ocultar botones (salvo que el semáforo esté justo en el nivel esperado)
                try:
                    id_usuario_actual = int(sess.id_usuario)
                    rechazo_usuario = db.query(Validacion).filter(
                        Validacion.Id_Periodo == periodo_id,
                        Validacion.Id_Usuario == id_usuario_actual,
                        Validacion.Id_Formato == 3,
                        Validacion.Validado == 0
                    ).first()
                    if rechazo_usuario:
                        if not puede_validar:
                            usuario_ya_rechazo = True
                except Exception:
                    # Si algo falla aquí, no bloqueamos por seguridad de UI
                    pass
        except Exception:
            # Si algo falla, solo no mostramos estado (UI seguirá normal)
            pass

        # Id de la UA que esta siendo evaluada no de la sesión del usuario, sino de la captura que se está mostrando
        id_unidad_academica = 0

        if unidad and unidad.strip():
            # Buscamos en tu modelo de Unidad Académica
            ua_obj = db.query(Unidad_Academica).filter(
                (Unidad_Academica.Sigla == unidad.strip()) | 
                (Unidad_Academica.Nombre == unidad.strip())
            ).first()
            if ua_obj:
                id_unidad_academica = ua_obj.Id_Unidad_Academica
            if not id_unidad_academica:
                id_unidad_academica = int(sess.id_unidad_academica) if getattr(sess, 'id_unidad_academica', None) else 0

        usuarios_registrados = obtener_encargados(db, id_unidad_academica, 3, id_nivel_evaluar)
        nombre_capturista = usuarios_registrados["nombre_capturista"]
        nombre_ceget = usuarios_registrados["nombre_ceget"]
        nombre_titular = usuarios_registrados["nombre_titular"]

        print(f"Capturista: {nombre_capturista}, CEGET: {nombre_ceget}, Titular: {nombre_titular}")

        if not egresados_data:
            return templates.TemplateResponse(nombre_template, {
                "request": request,
                "nombre_usuario": nombre_completo,
                "nombre_rol": nombre_rol,
                "id_rol": id_rol,
                "periodo": periodo,
                "periodo_id": periodo_id,
                "nivel": final_nivel,
                "unidad": final_unidad,
                "datos_resumen": [],
                "generaciones": [],
                "boletas_columnas": [],
                "filas_pivot": [],
                "modalidades_columnas": [],
                "filas_boleta_modalidad": [],
                "programa_counts": {},
                "turnos_columnas": [],
                "edades_columnas": [],
                "filas_edad_turno": [],
                "programa_counts_edad": {},
                "total_general": {"boletas": {}, "total_h": 0, "total_m": 0, "total_t": 0},
                "nombre_capturista": nombre_capturista,
                "nombre_ceget": nombre_ceget,
                "nombre_titular": nombre_titular,
                "puede_validar": puede_validar,
                "usuario_ya_valido": usuario_ya_valido,
                "usuario_ya_rechazo": usuario_ya_rechazo,
                "esperando_por_rol": esperando_por_rol,
                "error_message": "No hay datos disponibles para los filtros seleccionados",
                "exportando_pdf": exportando_pdf,
                "fecha_hoy": fecha_hoy,
                "session": sess
            })

        print(f"📊 Total de registros del SP: {len(egresados_data)}")

        def _get_row_value(row: dict, *keys, default=None):
            """Obtiene un valor del row soportando variantes de nombre de columna."""
            for key in keys:
                if key in row and row[key] is not None and str(row[key]).strip() != "":
                    return row[key]

            normalized = {
                ''.join(ch for ch in str(k).lower() if ch.isalnum()): v
                for k, v in row.items()
            }
            for key in keys:
                norm_key = ''.join(ch for ch in str(key).lower() if ch.isalnum())
                value = normalized.get(norm_key)
                if value is not None and str(value).strip() != "":
                    return value

            return default

        # === PROCESAR DATOS PARA EL RESUMEN DINÁMICO ===
        from collections import defaultdict
        
        # 1. Extraer generaciones únicas y ordenarlas
        generaciones_set = set()
        for row in egresados_data:
            gen = _get_row_value(row, 'Generacion', 'Generación')
            if gen:
                generaciones_set.add(str(gen))
        
        generaciones = sorted(list(generaciones_set), reverse=True)  # Más reciente primero
        print(f"📅 Generaciones detectadas: {generaciones}")
        
        # Determinar cuál es la generación regular (la más reciente)
        generacion_regular = generaciones[0] if generaciones else None
        print(f"📌 Generación REGULAR: {generacion_regular} (más reciente)")
        
        # 2. Estructura para agrupar datos por Programa → Modalidad → Boleta
        # estructura[programa][modalidad][boleta] = {...datos por generación...}
        estructura: Dict[str, Dict[str, Dict[str, Dict[str, Any]]]] = {}
        
        # 3. Procesar cada registro del SP
        for row in egresados_data:
            programa = str(_get_row_value(row, 'Nombre_Programa', 'Programa', default='Sin Programa')).strip() or 'Sin Programa'
            modalidad = str(_get_row_value(row, 'Modalidad', default='Sin Modalidad')).strip() or 'Sin Modalidad'
            generacion = str(_get_row_value(row, 'Generacion', 'Generación', default='Sin generación')).strip() or 'Sin generación'
            boleta_raw = _get_row_value(row, 'Boleta', default='S/B')
            boleta = str(boleta_raw).strip() if boleta_raw is not None else 'S/B'
            if not boleta:
                boleta = 'S/B'
            
            # Mapear Sexo: "HOMBRE" -> "H", "MUJER" -> "M"
            sexo_raw = str(_get_row_value(row, 'Sexo', default='M')).upper()
            if 'HOMBRE' in sexo_raw or sexo_raw == 'H':
                sexo = 'H'
            elif 'MUJER' in sexo_raw or sexo_raw == 'M':
                sexo = 'M'
            else:
                sexo = 'M'  # Default
            
            egresados_raw = _get_row_value(row, 'Egresados', default=0)
            try:
                egresados = int(float(egresados_raw)) if egresados_raw not in (None, '') else 0
            except (TypeError, ValueError):
                egresados = 0
            
            # Determinar si es Regular o Extemporáneo desde el campo Generacion
            # Si viene "Generación Regular" o contiene "Regular" -> regular
            # Si viene "Generación Extemporanea" o años antiguos -> extemporaneo
            generacion_lower = generacion.lower()
            if 'regular' in generacion_lower:
                tipo_key = 'regular'
            elif 'extemporanea' in generacion_lower or 'extemporaneo' in generacion_lower:
                tipo_key = 'extemporaneo'
            else:
                # Fallback: generación más reciente es regular
                tipo_key = 'regular' if generacion == generacion_regular else 'extemporaneo'
            
            #print(f"  📝 {programa} | {modalidad} | Bol:{boleta} | Gen:{generacion} ({tipo_key}) | {sexo}: {egresados}")
            
            # Inicializar estructura jerárquica de forma explícita
            programa_data = estructura.setdefault(programa, {})
            modalidad_data = programa_data.setdefault(modalidad, {})
            if boleta not in modalidad_data:
                modalidad_data[boleta] = {
                    'generaciones': {},
                    'total_h': 0,
                    'total_m': 0,
                    'total_t': 0
                }

            boleta_data = modalidad_data[boleta]
            generaciones_data = boleta_data['generaciones']
            if generacion not in generaciones_data:
                generaciones_data[generacion] = {
                    'regular': {'H': 0, 'M': 0, 'T': 0},
                    'extemporaneo': {'H': 0, 'M': 0, 'T': 0}
                }

            # Acumular egresados por generación y tipo
            generaciones_data[generacion][tipo_key][sexo] += egresados
            generaciones_data[generacion][tipo_key]['T'] += egresados

            # Acumular totales generales de esta boleta
            boleta_data['total_' + sexo.lower()] += egresados
            boleta_data['total_t'] += egresados
        
        # 4. Convertir estructura a lista para el template
        # Cada fila = Programa + Modalidad + Boleta literal
        datos_resumen = []
        for programa in sorted(estructura.keys()):
            for modalidad in sorted(estructura[programa].keys()):
                # Obtener todas las boletas de esta modalidad y ordenarlas numéricamente
                boletas_dict = estructura[programa][modalidad]
                boletas_ordenadas = sorted(
                    boletas_dict.keys(),
                    key=lambda x: (0, int(str(x))) if str(x).isdigit() else (1, str(x))
                )
                
                for boleta in boletas_ordenadas:
                    datos_boleta = boletas_dict[boleta]
                    
                    # Preparar datos de generaciones en el orden correcto
                    gen_data = []
                    for gen in generaciones:
                        gen_values = datos_boleta['generaciones'].get(gen, {
                            'regular': {'H': 0, 'M': 0, 'T': 0},
                            'extemporaneo': {'H': 0, 'M': 0, 'T': 0}
                        })
                        gen_data.append({
                            'generacion': gen,
                            'regular': gen_values['regular'],
                            'extemporaneo': gen_values['extemporaneo']
                        })
                    
                    datos_resumen.append({
                        'programa': programa,
                        'modalidad': modalidad,
                        'boleta': boleta,  # Boleta literal (1, 2, 3, etc.)
                        'generaciones': gen_data,
                        'total_h': datos_boleta['total_h'],
                        'total_m': datos_boleta['total_m'],
                        'total_t': datos_boleta['total_t']
                    })

        # 5. Construir estructura pivotada: filas por Programa+Modalidad y boletas como columnas
        boletas_global = set()
        for programa in estructura:
            for modalidad in estructura[programa]:
                boletas_global.update(estructura[programa][modalidad].keys())

        boletas_columnas = sorted(
            list(boletas_global),
            key=lambda x: (0, int(str(x))) if str(x).isdigit() else (1, str(x))
        )

        filas_pivot = []
        total_general = {
            'boletas': {
                b: {
                    'regular': {'H': 0, 'M': 0, 'T': 0},
                    'extemporaneo': {'H': 0, 'M': 0, 'T': 0}
                } for b in boletas_columnas
            },
            'total_h': 0,
            'total_m': 0,
            'total_t': 0
        }

        for programa in sorted(estructura.keys()):
            for modalidad in sorted(estructura[programa].keys()):
                boletas_data = {}
                row_total_h = 0
                row_total_m = 0
                row_total_t = 0

                for boleta in boletas_columnas:
                    if boleta in estructura[programa][modalidad]:
                        datos_boleta = estructura[programa][modalidad][boleta]

                        regular_h = regular_m = regular_t = 0
                        ext_h = ext_m = ext_t = 0

                        for _, gen_values in datos_boleta['generaciones'].items():
                            regular_h += gen_values['regular']['H']
                            regular_m += gen_values['regular']['M']
                            regular_t += gen_values['regular']['T']

                            ext_h += gen_values['extemporaneo']['H']
                            ext_m += gen_values['extemporaneo']['M']
                            ext_t += gen_values['extemporaneo']['T']

                        boletas_data[boleta] = {
                            'regular': {'H': regular_h, 'M': regular_m, 'T': regular_t},
                            'extemporaneo': {'H': ext_h, 'M': ext_m, 'T': ext_t}
                        }

                        row_total_h += regular_h + ext_h
                        row_total_m += regular_m + ext_m
                        row_total_t += regular_t + ext_t

                        total_general['boletas'][boleta]['regular']['H'] += regular_h
                        total_general['boletas'][boleta]['regular']['M'] += regular_m
                        total_general['boletas'][boleta]['regular']['T'] += regular_t
                        total_general['boletas'][boleta]['extemporaneo']['H'] += ext_h
                        total_general['boletas'][boleta]['extemporaneo']['M'] += ext_m
                        total_general['boletas'][boleta]['extemporaneo']['T'] += ext_t
                    else:
                        boletas_data[boleta] = {
                            'regular': {'H': 0, 'M': 0, 'T': 0},
                            'extemporaneo': {'H': 0, 'M': 0, 'T': 0}
                        }

                total_general['total_h'] += row_total_h
                total_general['total_m'] += row_total_m
                total_general['total_t'] += row_total_t

                filas_pivot.append({
                    'programa': programa,
                    'modalidad': modalidad,
                    'boletas': boletas_data,
                    'total_h': row_total_h,
                    'total_m': row_total_m,
                    'total_t': row_total_t
                })
        
        print(f"✅ Resumen procesado: {len(datos_resumen)} filas (Programa+Modalidad+Boleta)")
        print(f"📊 Generaciones: {len(generaciones)}")
        print(f"📊 Boletas en columnas: {len(boletas_columnas)}")
        print(f"📊 Filas pivotadas (Programa+Modalidad): {len(filas_pivot)}")
        
        
        # ============================================================
        # 6. TABLAS DINÁMICAS (NUEVO FORMATO)
        #    Tabla 1: Programa | Generación | Boleta | Modalidad(H/M/T...) | Total(H/M/T)
        #    Tabla 2: Programa | Generación | Edad   | Turno(H/M/T...)     | Total(H/M/T)
        # ============================================================
        from collections import defaultdict

        def _is_nullish(v) -> bool:
            if v is None:
                return True
            s = str(v).strip()
            return (s == "" or s.upper() in ("NULL", "NONE", "N/A", "NA"))

        modalidades_set = set()
        boletas_set = set()
        turnos_set = set()
        edades_set = set()

        # data_boleta[programa][tipo][boleta][modalidad] = {'H':..,'M':..,'T':..}
        data_boleta = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {'H': 0, 'M': 0, 'T': 0}))))

        # data_edad[programa][tipo][edad][turno] = {'H':..,'M':..,'T':..}
        data_edad = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {'H': 0, 'M': 0, 'T': 0}))))

        for row in egresados_data:
            programa = str(_get_row_value(row, 'Nombre_Programa', 'Programa', default='Sin Programa')).strip() or 'Sin Programa'
            modalidad = str(_get_row_value(row, 'Modalidad', default='Sin Modalidad')).strip() or 'Sin Modalidad'
            generacion = str(_get_row_value(row, 'Generacion', 'Generación', default='')).strip()

            # Boleta (filtrar nulls)
            boleta_raw = _get_row_value(row, 'Boleta', default=None)
            if _is_nullish(boleta_raw):
                continue
            boleta = str(boleta_raw).strip()

            # Sexo
            sexo_raw = str(_get_row_value(row, 'Sexo', default='M')).upper()
            if 'HOMBRE' in sexo_raw or sexo_raw == 'H':
                sexo = 'H'
            elif 'MUJER' in sexo_raw or sexo_raw == 'M':
                sexo = 'M'
            else:
                sexo = 'M'

            # Egresados (ya NO se descartan los ceros: si una combinación de
            # catálogo no tiene egresados, igual debe aparecer con 0 en las
            # tablas de Modalidad/Turno/Edad, igual que ya pasa en Boleta y Programa)
            eg_raw = _get_row_value(row, 'Egresados', default=0)
            try:
                eg = int(float(eg_raw)) if eg_raw not in (None, '') else 0
            except (TypeError, ValueError):
                eg = 0

            # Tipo de generación (regular/extemporaneo)
            generacion_lower = generacion.lower()
            if 'extemporanea' in generacion_lower or 'extemporaneo' in generacion_lower:
                tipo = 'extemporaneo'
            elif 'regular' in generacion_lower:
                tipo = 'regular'
            else:
                # fallback con la generación más reciente detectada
                tipo = 'regular' if generacion and generacion == generacion_regular else 'extemporaneo'

            modalidades_set.add(modalidad)
            boletas_set.add(boleta)

            # Tabla 1 acumula por boleta + modalidad
            celda = data_boleta[programa][tipo][boleta][modalidad]
            celda[sexo] += eg
            celda['T'] += eg

            # Tabla 2 acumula por edad + turno (si existen)
            # Intentar primero Grupo_Edad, luego Edad como fallback
            edad_raw = _get_row_value(row, 'Grupo_Edad', 'Edad', default=None)
            turno_raw = _get_row_value(row, 'Turno', default=None)
            if not _is_nullish(edad_raw) and not _is_nullish(turno_raw):
                edad = str(edad_raw).strip()
                turno = str(turno_raw).strip()
                edades_set.add(edad)
                turnos_set.add(turno)

                celda2 = data_edad[programa][tipo][edad][turno]
                celda2[sexo] += eg
                celda2['T'] += eg

        # Columnas ordenadas
        modalidades_columnas = sorted(list(modalidades_set))

        boletas_columnas_row = sorted(
            list(boletas_set),
            key=lambda x: (0, int(str(x))) if str(x).isdigit() else (1, str(x))
        )

        def _sort_mixed_numbers(values):
            def key(v):
                s = str(v).strip()
                return (0, int(s)) if s.isdigit() else (1, s)
            return sorted(values, key=key)

        turnos_columnas = sorted(list(turnos_set))
        edades_columnas = _sort_mixed_numbers(list(edades_set))

        # Inicializar totales generales SIEMPRE (incluso si no hay datos)
        totales_tabla1 = {'modalidades': {}, 'total_h': 0, 'total_m': 0, 'total_t': 0}
        totales_tabla2 = {'turnos': {}, 'total_h': 0, 'total_m': 0, 'total_t': 0}
        
        # Inicializar estructuras para modalidades y turnos
        for mod in modalidades_columnas:
            totales_tabla1['modalidades'][mod] = {'H': 0, 'M': 0, 'T': 0}
        for turno in turnos_columnas:
            totales_tabla2['turnos'][turno] = {'H': 0, 'M': 0, 'T': 0}
        
        # Inicializar subtotales por generación
        subtotales_generacion_tabla1 = {
            'regular': {'modalidades': {}, 'total_h': 0, 'total_m': 0, 'total_t': 0},
            'extemporaneo': {'modalidades': {}, 'total_h': 0, 'total_m': 0, 'total_t': 0}
        }
        subtotales_generacion_tabla2 = {
            'regular': {'turnos': {}, 'total_h': 0, 'total_m': 0, 'total_t': 0},
            'extemporaneo': {'turnos': {}, 'total_h': 0, 'total_m': 0, 'total_t': 0}
        }
        
        # Inicializar modalidades y turnos para cada tipo de generación
        for tipo in ['regular', 'extemporaneo']:
            for mod in modalidades_columnas:
                subtotales_generacion_tabla1[tipo]['modalidades'][mod] = {'H': 0, 'M': 0, 'T': 0}
            for turno in turnos_columnas:
                subtotales_generacion_tabla2[tipo]['turnos'][turno] = {'H': 0, 'M': 0, 'T': 0}

        # Construir filas para Tabla 1
        filas_boleta_modalidad = []
        programa_counts = {}
        
        for programa in sorted(data_boleta.keys()):
            reg_boletas = _sort_mixed_numbers(list(data_boleta[programa].get('regular', {}).keys()))
            ext_boletas = _sort_mixed_numbers(list(data_boleta[programa].get('extemporaneo', {}).keys()))

            programa_counts[programa] = {
                'regular': len(reg_boletas),
                'extemporaneo': len(ext_boletas),
                "error_message": "No hay datos disponibles para este acuse",
                "session": sess,
            }

            for tipo, boletas_lista in (('regular', reg_boletas), ('extemporaneo', ext_boletas)):
                for boleta in boletas_lista:
                    modalidades_data = {}
                    total_h = total_m = total_t = 0

                    for mod in modalidades_columnas:
                        v = data_boleta[programa][tipo][boleta].get(mod, {'H': 0, 'M': 0, 'T': 0})
                        modalidades_data[mod] = v
                        total_h += v.get('H', 0)
                        total_m += v.get('M', 0)
                        total_t += v.get('T', 0)
                        
                        # Acumular en totales globales
                        totales_tabla1['modalidades'][mod]['H'] += v.get('H', 0)
                        totales_tabla1['modalidades'][mod]['M'] += v.get('M', 0)
                        totales_tabla1['modalidades'][mod]['T'] += v.get('T', 0)
                        
                        # Acumular en subtotales por generación
                        subtotales_generacion_tabla1[tipo]['modalidades'][mod]['H'] += v.get('H', 0)
                        subtotales_generacion_tabla1[tipo]['modalidades'][mod]['M'] += v.get('M', 0)
                        subtotales_generacion_tabla1[tipo]['modalidades'][mod]['T'] += v.get('T', 0)

                    totales_tabla1['total_h'] += total_h
                    totales_tabla1['total_m'] += total_m
                    totales_tabla1['total_t'] += total_t
                    
                    # Acumular en subtotales por generación
                    subtotales_generacion_tabla1[tipo]['total_h'] += total_h
                    subtotales_generacion_tabla1[tipo]['total_m'] += total_m
                    subtotales_generacion_tabla1[tipo]['total_t'] += total_t

                    filas_boleta_modalidad.append({
                        'programa': programa,
                        'tipo': tipo,
                        'boleta': boleta,
                        'modalidades': modalidades_data,
                        'total_h': total_h,
                        'total_m': total_m,
                        'total_t': total_t
                    })

        # Construir filas para Tabla 2
        filas_edad_turno = []
        programa_counts_edad = {}

        for programa in sorted(data_edad.keys()):
            reg_edades = _sort_mixed_numbers(list(data_edad[programa].get('regular', {}).keys()))
            ext_edades = _sort_mixed_numbers(list(data_edad[programa].get('extemporaneo', {}).keys()))

            programa_counts_edad[programa] = {
                'regular': len(reg_edades),
                'extemporaneo': len(ext_edades),
                'total': len(reg_edades) + len(ext_edades)
            }

            for tipo, edades_lista in (('regular', reg_edades), ('extemporaneo', ext_edades)):
                for edad in edades_lista:
                    turnos_data = {}
                    total_h = total_m = total_t = 0

                    for turno in turnos_columnas:
                        v = data_edad[programa][tipo][edad].get(turno, {'H': 0, 'M': 0, 'T': 0})
                        turnos_data[turno] = v
                        total_h += v.get('H', 0)
                        total_m += v.get('M', 0)
                        total_t += v.get('T', 0)
                        
                        # Acumular en totales globales
                        totales_tabla2['turnos'][turno]['H'] += v.get('H', 0)
                        totales_tabla2['turnos'][turno]['M'] += v.get('M', 0)
                        totales_tabla2['turnos'][turno]['T'] += v.get('T', 0)
                        
                        # Acumular en subtotales por generación
                        subtotales_generacion_tabla2[tipo]['turnos'][turno]['H'] += v.get('H', 0)
                        subtotales_generacion_tabla2[tipo]['turnos'][turno]['M'] += v.get('M', 0)
                        subtotales_generacion_tabla2[tipo]['turnos'][turno]['T'] += v.get('T', 0)

                    totales_tabla2['total_h'] += total_h
                    totales_tabla2['total_m'] += total_m
                    totales_tabla2['total_t'] += total_t
                    
                    # Acumular en subtotales por generación
                    subtotales_generacion_tabla2[tipo]['total_h'] += total_h
                    subtotales_generacion_tabla2[tipo]['total_m'] += total_m
                    subtotales_generacion_tabla2[tipo]['total_t'] += total_t

                    filas_edad_turno.append({
                        'programa': programa,
                        'tipo': tipo,
                        'edad': edad,
                        'turnos': turnos_data,
                        'total_h': total_h,
                        'total_m': total_m,
                        'total_t': total_t
                    })

        # === Simplificar filas_edad_turno para evitar duplicados (edad 19 repetida) ===
        # Agrupar edades globalmente
        edades_agrupadas = {}
        for fila in filas_edad_turno:
            edad = fila['edad']
            if edad not in edades_agrupadas:
                edades_agrupadas[edad] = {'H': 0, 'M': 0, 'T': 0}
            edades_agrupadas[edad]['H'] += fila['total_h']
            edades_agrupadas[edad]['M'] += fila['total_m']
            edades_agrupadas[edad]['T'] += fila['total_t']
        
        filas_edad_turno_simple = []
        for edad in _sort_mixed_numbers(list(edades_agrupadas.keys())):
            totales = edades_agrupadas[edad]
            filas_edad_turno_simple.append({
                'edad': edad,
                'total_h': totales['H'],
                'total_m': totales['M'],
                'total_t': totales['T']
            })
        filas_edad_turno = filas_edad_turno_simple
        totales_tabla2['edades'] = edades_agrupadas

        # === Layout fijo de dos columnas: izq (Boleta+Edad), der (Programa+otras) ===
        col_left = ['Boleta', 'GrupoEdad']
        col_right = ['Programa', 'Modalidad', 'Generacion', 'Turno']
        max_len = max(len(col_left), len(col_right))
        tablas_filas = []
        for i in range(max_len):
            left = col_left[i] if i < len(col_left) else None
            right = col_right[i] if i < len(col_right) else None
            tablas_filas.append((left, right))

        id_periodo_anterior, periodo_anterior_literal = get_periodo_anterior_al_ultimo(db)

        return templates.TemplateResponse(nombre_template, {
            "request": request,
            "nombre_usuario": nombre_completo,
            "nombre_rol": nombre_rol,
            "id_rol": id_rol,
            "periodo": periodo,
            "periodo_id": periodo_id,
            "periodo_anterior": periodo_anterior_literal,
            "nivel": final_nivel,
            "unidad": final_unidad,
            "datos_resumen": datos_resumen,
            "generaciones": generaciones,
            "boletas_columnas": boletas_columnas,
            "filas_pivot": filas_pivot,
            "total_general": total_general,
            "puede_validar": puede_validar,
            "usuario_ya_valido": usuario_ya_valido,
            "usuario_ya_rechazo": usuario_ya_rechazo,
            "esperando_por_rol": esperando_por_rol,
            "modalidades_columnas": modalidades_columnas,
            "filas_boleta_modalidad": filas_boleta_modalidad,
            "programa_counts": programa_counts,
            "turnos_columnas": turnos_columnas,
            "edades_columnas": edades_columnas,
            "filas_edad_turno": filas_edad_turno,
            "programa_counts_edad": programa_counts_edad,
            "tablas_filas": tablas_filas,
            "totales_tabla1": totales_tabla1,
            "totales_tabla2": totales_tabla2,
            "subtotales_generacion_tabla1": subtotales_generacion_tabla1,
            "subtotales_generacion_tabla2": subtotales_generacion_tabla2,
            "nombre_capturista": nombre_capturista,
            "nombre_ceget": nombre_ceget,
            "nombre_titular": nombre_titular,
            "estado_semaforo_actual": estado_semaforo if ('estado_semaforo' in locals() and estado_semaforo is not None) else 0,
            "no_validado": (estado_semaforo is None or estado_semaforo < 9) if ('estado_semaforo' in locals() and estado_semaforo is not None) else True,
            "error_message": None,
            "exportando_pdf": exportando_pdf,
            "fecha_hoy": fecha_hoy,
            "session": sess
        })
        
    except Exception as e:
        print(f"[egresados] Error en resumen dinamico: {str(e)}")
        import traceback
        traceback.print_exc()
        return templates.TemplateResponse(nombre_template, {
            "request": request,
            "nombre_usuario": nombre_completo,
            "nombre_rol": nombre_rol,
            "id_rol": id_rol,
            "periodo": periodo,
            "periodo_id": periodo_id,
            "periodo_anterior": periodo_anterior_literal,
            "nivel": final_nivel,
            "unidad": final_unidad,
            "datos_resumen": [],
            "generaciones": [],
            "boletas_columnas": [],
            "filas_pivot": [],
            "modalidades_columnas": [],
            "filas_edad_turno": [],
            "turnos_columnas": [],
            "total_general": {"boletas": {}, "total_h": 0, "total_m": 0, "total_t": 0},
            "totales_tabla1": {"modalidades": {}, "total_h": 0, "total_m": 0, "total_t": 0},
            "totales_tabla2": {"turnos": {}, "total_h": 0, "total_m": 0, "total_t": 0},
            "subtotales_generacion_tabla1": {"regular": {"modalidades": {}, "total_h": 0, "total_m": 0, "total_t": 0}, "extemporaneo": {"modalidades": {}, "total_h": 0, "total_m": 0, "total_t": 0}},
            "subtotales_generacion_tabla2": {"regular": {"turnos": {}, "total_h": 0, "total_m": 0, "total_t": 0}, "extemporaneo": {"turnos": {}, "total_h": 0, "total_m": 0, "total_t": 0}},
            "puede_validar": False,
            "usuario_ya_valido": False,
            "usuario_ya_rechazo": False,
            "esperando_por_rol": None,
            "tablas_filas": [],
            "nombre_capturista": None,
            "nombre_ceget": None,
            "nombre_titular": None,
            "error_message": f"Error al procesar datos: {str(e)}",
            "exportando_pdf": exportando_pdf,
            "fecha_hoy": fecha_hoy,
            "session": sess
        })

@router.get('/acuse-validacion/pdf')
async def exportar_acuse_egresados_pdf(
    request: Request,
    periodo: str = None,
    nivel: str = None,
    unidad: str = None,
    sess=Depends(validar_acuse),
    db: Session = Depends(get_db)
):
    """
    Genera y descarga el PDF del Acuse de Validación de Egresados.
    Reutiliza la misma vista de resumen dinámico (vista='acuse') pero
    renderizada en modo impresión (exportando_pdf=True), igual que se
    hace para el acuse de Matrícula.
    """
    # Resolver sigla limpia de la unidad académica
    ua_sigla = (unidad or sess.sigla_unidad_academica or '').strip()
    if ua_sigla:
        ua_obj = db.query(Unidad_Academica).filter(
            (Unidad_Academica.Sigla == ua_sigla) | (Unidad_Academica.Nombre == ua_sigla)
        ).first()
        if ua_obj and ua_obj.Sigla:
            ua_sigla = ua_obj.Sigla

    # Resolver periodo limpio
    periodo_str = (periodo or '').strip()
    if not periodo_str:
        _, periodo_str = get_ultimo_periodo(db)

    resp = await resumen_egresados_dinamico_view(
        request=request,
        periodo=periodo,
        nivel=nivel,
        unidad=unidad,
        sess=sess,
        db=db,
        vista='acuse',
        exportando_pdf=True
    )

    if isinstance(resp, RedirectResponse):
        return resp

    if isinstance(resp.body, memoryview):
        html_text = resp.body.tobytes().decode('utf-8')
    else:
        html_text = bytes(resp.body).decode('utf-8')

    base_path = Path(__file__).resolve().parents[2] / 'frontend' / 'static'
    ruta_css = base_path / 'css' / 'components' / 'matricula_acuse.css'

    if not ruta_css.exists():
        raise HTTPException(
            status_code=500,
            detail=f"No se encontró el archivo CSS en: {ruta_css}."
        )

    try:
        pdf_bytes = weasyprint.HTML(string=html_text, base_url=str(base_path)).write_pdf(
            stylesheets=[
                weasyprint.CSS(filename=str(ruta_css)),
                weasyprint.CSS(string='@page { size: Letter; margin: 0.9cm 1.2cm 2.9cm 1.2cm; }')
            ]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando PDF: {str(e)}")

    unidad_limpia = str(ua_sigla).replace(' ', '_').strip()
    periodo_limpio = str(periodo_str).replace('/', '_').replace(' ', '_').strip()
    filename = f"acuse_egresados_{unidad_limpia}_{periodo_limpio}.pdf"
    
    return Response(content=pdf_bytes, media_type='application/pdf', headers={
        'Content-Disposition': f'attachment; filename="{filename}"'
    })


@router.get('/exportar-excel-egresados')
async def exportar_egresados_excel(
    request: Request,
    periodo: str,
    nivel: str,
    unidad: str,
    sess=Depends(validar_acuse),
    db: Session = Depends(get_db)
):
    """
    Exporta a Excel los datos de SP_Consulta_Egresados_Unidad_Academica.
    Filtra ÚNICAMENTE aquellos registros que tengan en la columna de Egresados > 0 (omitiendo los '0').
    """
    import io
    import xlsxwriter
    from fastapi.responses import StreamingResponse

    # Resolver sigla limpia de la unidad académica
    ua_sigla = (unidad or sess.sigla_unidad_academica or '').strip()
    if ua_sigla:
        ua_obj = db.query(Unidad_Academica).filter(
            (Unidad_Academica.Sigla == ua_sigla) | (Unidad_Academica.Nombre == ua_sigla)
        ).first()
        if ua_obj and ua_obj.Sigla:
            ua_sigla = ua_obj.Sigla

    # Resolver periodo limpio
    periodo_str = (periodo or '').strip()
    if not periodo_str:
        _, periodo_str = get_ultimo_periodo(db)

    host = get_request_host(request)
    nombre_completo = " ".join(filter(None, [sess.nombre_usuario, sess.apellidoP_usuario, sess.apellidoM_usuario]))

    egresados_data, _ = execute_egresados_sp(
        db=db,
        unidad_sigla=ua_sigla,
        periodo_literal=periodo_str,
        nivel_nombre=nivel,
        usuario=nombre_completo or sess.usuario,
        host=host
    )

    # Filtrar solo registros donde Egresados > 0
    rows_filtradas = []
    for row in egresados_data:
        val = row.get('Egresados')
        try:
            num = int(float(val)) if val not in (None, '') else 0
        except (ValueError, TypeError):
            num = 0
        if num > 0:
            rows_filtradas.append(row)

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    ws = workbook.add_worksheet("Egresados")

    if rows_filtradas:
        headers = [k for k in rows_filtradas[0].keys() if str(k).lower() not in ('id_semaforo', 'id_semaforo_actual')]
        header_format = workbook.add_format({'bold': True, 'bg_color': '#750946', 'font_color': '#FFFFFF'})
        for col, h in enumerate(headers):
            ws.write(0, col, h, header_format)
        for row_idx, row in enumerate(rows_filtradas, start=1):
            for col_idx, key in enumerate(headers):
                ws.write(row_idx, col_idx, row.get(key, ''))
    else:
        ws.write(0, 0, "No hay datos de egresados mayores a 0 para los filtros seleccionados")

    workbook.close()
    output.seek(0)

    unidad_limpia = str(ua_sigla).replace(' ', '_').strip()
    periodo_limpio = str(periodo_str).replace('/', '_').replace(' ', '_').strip()
    nivel_limpio = str(nivel).replace(' ', '_').strip()
    filename = f"Egresados_{unidad_limpia}_{nivel_limpio}_{periodo_limpio}.xlsx"

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.post("/fijar-nivel-temporal")
async def fijar_nivel_temporal(
    request: Request, 
    data: dict, 
    sess: SessionData = Depends(get_current_session),
    db: Session = Depends(get_db)
):
    id_nuevo_raw = data.get("id_nivel")
    nombre_nuevo = data.get("nombre_nivel")
    
    id_nuevo = 0
    try:
        id_nuevo = int(id_nuevo_raw)
    except (ValueError, TypeError):
        nivel_obj = db.query(Nivel).filter(Nivel.Nivel == nombre_nuevo).first()
        if nivel_obj:
            id_nuevo = nivel_obj.Id_Nivel
            
    from dataclasses import replace
    nueva_sesion = replace(sess, id_nivel=id_nuevo, nombre_nivel=nombre_nuevo)
    
    session_id = request.cookies.get("session_id")
    if session_id:
        session_store.update_data(session_id, nueva_sesion)
        return {"status": "ok"}
    
    raise HTTPException(status_code=400, detail="Sesión no encontrada")