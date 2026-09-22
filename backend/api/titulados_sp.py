from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text 
from sqlalchemy import select
from collections import defaultdict
from fastapi.responses import RedirectResponse, FileResponse, Response
from backend.api import unidad_academica
from backend.database.connection import get_db
from backend.core.templates import templates
from backend.schemas import Nivel
from backend.services import notificacion
from backend.services.titulados_service import obtener_titulados, preparar_datos_temp_titulados, preparar_datos_temp_titulados_desde_db, procesar_titulados
from backend.crud.ConsultaTitulados import get_titulados, insertar_temp_titulados, insertar_titulados_sp, finalizar_captura_programa_modalidad, verificar_todos_programas_finalizados, finalizar_unidad_academica
from backend.services.periodo_service import get_periodo_activo, get_periodo_anterior_al_ultimo, get_ultimo_periodo
from backend.core.auth import get_current_session
from backend.database.models.CatPeriodo import CatPeriodo as Periodo
from backend.database.models.Temp_Titulados import Temp_Titulados
from backend.database.models.CatUnidadAcademica import CatUnidadAcademica as Unidad_Academica
from backend.database.models.Usuario import Usuario
from backend.database.models.SemaforoUnidadAcademica import SemaforoUnidadAcademica
from backend.database.models.CatRoles import CatRoles
from backend.database.models.CatNivel import CatNivel as Nivel
from backend.database.models.UnidadProgramaModalidad import CatUnidadProgramaModalidad
from backend.database.models.CatProgramas import CatProgramas
from backend.database.models.ProgramaModalidad import ProgramaModalidad
from backend.database.models.Validacion import Validacion
from pydantic import BaseModel
from typing import List, Optional
from backend.utils.request import get_request_host
from backend.services.encargado_ua_service import obtener_encargados, verificar_permiso_formato
from backend.services.envio_correo_service import (
    notificar_rechazo_global,
    obtener_correos_involucrados,
    enviar_correo_acuse_titular,
    verificar_todos_modulos_validados_titular,
)
from backend.core.auth import VerificarAccesoAcuse
validar_acuse = VerificarAccesoAcuse()
from backend.core.security_logger import registrar_bloqueo_seguridad
import traceback
import json
from pathlib import Path
from datetime import datetime

host = "Test"
fila = []

class FinalizarTituladosRequest(BaseModel):
    datos: Optional[List[dict]] = []
    programa: str
    modalidad: str
    origen: str

def valor_orden_edad(edad: str):
    edad = edad.strip()

    if edad.startswith("<="):
        return int(edad.replace("<=", "")) - 0.5

    if edad.startswith(">="):
        return int(edad.replace(">=", "")) + 0.5

    if edad.startswith("<"):
        return int(edad.replace("<", "")) - 0.5

    if edad.startswith(">"):
        return int(edad.replace(">", "")) + 0.5

    if "-" in edad:
        inicio = edad.split("-")[0]
        return int(inicio)

    return int(edad)

router = APIRouter()
validar_acuse = VerificarAccesoAcuse()

@router.get("/consulta", response_class=HTMLResponse)
async def consulta_titulados(
    request: Request,
    sess = Depends(validar_acuse),
    db: Session = Depends(get_db)
):
    
    id_rol = int(sess.id_rol)
    nombre_rol = sess.nombre_rol
    
    nombre = sess.nombre_usuario
    apellidoP_usuario = sess.apellidoP_usuario
    apellidoM_usuario = sess.apellidoM_usuario
    id_usuario = sess.id_usuario
    
    print("id usuario: ", id_usuario)

    nombre_usuario = sess.usuario
    sigla_unidad_academica = sess.sigla_unidad_academica
    id_unidad_academica = int(sess.id_unidad_academica)
   
    nombre_nivel = sess.nombre_nivel
    
    ua_usuario = None
    
    unidad_academica_usuario = None

    niveles_unidad = None
    niveles_por_unidad = None

    try:
        verificar_permiso_formato(db, id_usuario, 4, id_rol=id_rol)
    except HTTPException as e:
        return templates.TemplateResponse("error.html", {
        "request": request,
        "error_message": e.detail,
        "redirect_url": "/mod_principal/",
        "session": sess
        })


    if id_unidad_academica > 0:
            ua_usuario = db.query(Unidad_Academica).filter(
                Unidad_Academica.Id_Unidad_Academica == id_unidad_academica
            ).first()

            niveles_unidad = (
                db.query(
                    Unidad_Academica.Nombre,
                    Nivel.Nivel
                )
                .select_from(CatUnidadProgramaModalidad)
                .join(Unidad_Academica, Unidad_Academica.Id_Unidad_Academica == CatUnidadProgramaModalidad.Id_Unidad_Academica)
                .join(ProgramaModalidad, ProgramaModalidad.Id_Modalidad_Programa == CatUnidadProgramaModalidad.Id_Modalidad_Programa)
                .join(CatProgramas, CatProgramas.Id_Programa == ProgramaModalidad.Id_Programa)
                .join(Nivel, Nivel.Id_Nivel == CatProgramas.Id_Nivel)
                .filter(CatUnidadProgramaModalidad.Id_Unidad_Academica == id_unidad_academica)
                .distinct()
                .all()
            )

    if ua_usuario:
        unidad_academica_usuario = ua_usuario.Nombre
    else:
        print(f"Advertencia: No se encontró la Unidad Académica con ID {id_unidad_academica} para el usuario {nombre_usuario}.")

    if niveles_unidad:
        niveles_por_unidad = [row.Nivel for row in niveles_unidad]
    
    nivel = sess.id_nivel

    print(unidad_academica_usuario)
    """
    unidad_academica = sess.unidad_academica
   
    nombre_nivel = getattr(sess, 'nombre_nivel', "Nivel de Prueba")
    nivel_acceso = getattr(sess, 'id_nivel', 0)
    usuario = getattr(sess, 'usuario', "usuario_prueba")"""

    print(f"Usuario: {nombre_usuario}, Rol: {nombre_rol} (ID: {id_rol}), Unidad Académica: {unidad_academica_usuario} ({sigla_unidad_academica}), Nivel: {nombre_nivel}, Host: {host}")
    try:
        periodo_id_anterior, periodo_anterior_literal = get_periodo_anterior_al_ultimo(db)
        periodo_id_actual, periodo_literal_actual = get_periodo_activo(db)
        if not periodo_id_actual or not periodo_literal_actual:
            periodo_id_actual, periodo_literal_actual = get_ultimo_periodo(db)

        periodo_default_literal = periodo_literal_actual
        print(f" Periodo activo (default): {periodo_default_literal} | Periodo anterior (header): {periodo_anterior_literal}")


    except Exception as e:
        print(f" Error al obtener periodo: {str(e)}")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_message": f"Error al cargar el periodo: {str(e)}",
            "redirect_url": "/mod_principal/",
            "session": sess
        })

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
    

    es_capturista = (id_rol == 3)
    es_validador = (id_rol in [4, 5, 6, 7, 8, 9])  
    es_rol_director = (id_rol in [4, 5])  
    es_rol_superior = (id_rol in [6, 7, 8, 9])  
    modo_vista = "captura" if es_capturista else "validacion"

    # Obtener periodos según el rol:
    # Roles 6-9 (y admin): Todos los periodos disponibles en la BD (incluso Id_Estatus == 0)
    # Roles 4-5 y capturistas: Únicamente periodos activos (Id_Estatus == 1)
    if es_rol_superior:
        periodos = db.query(Periodo).order_by(Periodo.Id_Periodo.desc()).all()
    else:
        periodos = db.query(Periodo).filter(Periodo.Id_Estatus == 1).order_by(Periodo.Id_Periodo.desc()).all()
    
    niveles = db.query(Nivel).filter(Nivel.Id_Estatus == 1).order_by(Nivel.Id_Nivel).all()
    

    query = (
        select(Unidad_Academica.Sigla , Unidad_Academica.Nombre, Nivel.Nivel)
        .distinct()
        .join(CatUnidadProgramaModalidad, CatUnidadProgramaModalidad.Id_Unidad_Academica == Unidad_Academica.Id_Unidad_Academica)
        .join(ProgramaModalidad, ProgramaModalidad.Id_Modalidad_Programa == CatUnidadProgramaModalidad.Id_Modalidad_Programa)
        .join(CatProgramas, CatProgramas.Id_Programa == ProgramaModalidad.Id_Programa)
        .join(Nivel, Nivel.Id_Nivel == CatProgramas.Id_Nivel)
        .order_by(Nivel.Nivel.desc())
    )

    rows = db.execute(query).all()

    resultado = defaultdict(list)
    for sigla, nombre, nivel in rows:
        resultado[nivel].append({"sigla": sigla, "nombre": nombre})
    resultado = dict(resultado)

    periodosDisponibles = [periodo.Periodo for periodo in periodos]
    nombres_niveles = [n.Nivel for n in niveles]
  
    contexto = {}
    filas = []
    rechazo_info = {}
    matricula_rechazada = False

    if es_capturista:
        try:
            print(
                f"Obteniendo titulados para UA: {sigla_unidad_academica}, "
                f"Periodo: {periodo_default_literal}, "
                f"Nivel: {nombre_nivel}, "
                f"Periodo anterior (id): {periodo_id_anterior}, " 
                f"Usuario: {nombre_usuario}"
            )

            rechazo_info = notificacion.notificacion_rechazo(
                db=db,
                periodo_anterior_id=periodo_id_anterior,
                Id_Unidad_Academica=id_unidad_academica,
                id_formato=4,
                id_nivel=getattr(sess, 'id_nivel', None))
            
            print("Esta es la info de rechzo: ", rechazo_info)
            
            if rechazo_info:
                matricula_rechazada = True

            contexto, filas = obtener_titulados(
                db=db,
                unidad_academica=sigla_unidad_academica,
                periodo=periodo_literal_actual,
                nivel=nombre_nivel,
                usuario=nombre_usuario,
                host=host,
            )

            if filas is None:
                filas = []

        except Exception as e:
            print(f"Error obteniendo titulados: {e}")
            contexto = {}
            filas = []
    else:
        rechazo_info = None

    # Catálogo de turnos únicos traídos desde el SP
    turnos_sp = sorted(list(set(r.get("Turno") for r in filas if r.get("Turno"))))
    if not turnos_sp:
        turnos_sp = ["Matutino", "Vespertino"]

    # Mapeo por programa_modalidad -> turnos
    programa_modalidad_turnos = {}
    for r in filas:
        prog = r.get("Nombre_Programa")
        mod = r.get("Modalidad")
        turno = r.get("Turno")
        if prog and mod and turno:
            key = f"{str(prog).strip()}_{str(mod).strip()}"
            if key not in programa_modalidad_turnos:
                programa_modalidad_turnos[key] = set()
            programa_modalidad_turnos[key].add(str(turno).strip())

    programa_modalidad_turnos = {k: sorted(list(v)) for k, v in programa_modalidad_turnos.items()}
    programa_modalidad_turnos_json = json.dumps(programa_modalidad_turnos)

    # Mapeo (Programa, Modalidad) -> Boletas para filtrado dinámico en el frontend
    programa_modalidad_boletas_raw = {}
    for r in filas:
        prog  = r.get("Nombre_Programa")
        mod   = r.get("Modalidad")
        bol   = r.get("Boleta")
        if prog and mod and bol is not None:
            key = f"{str(prog).strip()}_{str(mod).strip()}"
            if key not in programa_modalidad_boletas_raw:
                programa_modalidad_boletas_raw[key] = set()
            programa_modalidad_boletas_raw[key].add(str(bol).strip())

    def _sort_bol(s):
        try: return -int(v)
        except: return 0

    programa_modalidad_boletas = {
        k: sorted(list(v), key=lambda b: (-int(b) if b.lstrip('-').isdigit() else 0))
        for k, v in programa_modalidad_boletas_raw.items()
    }
    programa_modalidad_boletas_json = json.dumps(programa_modalidad_boletas)

    boletas = []
    try:
        # Extraer boletas únicas directamente desde los datos del SP
        boletas_raw = sorted(
            set(
                int(r["Boleta"])
                for r in filas
                if r.get("Boleta") is not None and str(r["Boleta"]).strip() != ""
            ),
            reverse=True  # Descendente (más reciente primero)
        )
        boletas = boletas_raw

        # Fallback: si el SP no retornó boletas, calcular aritméticamente desde el contexto
        if not boletas:
            boleta_base = contexto.get("Boleta")
            if boleta_base:
                boleta_base = int(boleta_base)
                boletas = list(range(boleta_base + 12, boleta_base, -1))
                print(f"Boletas calculadas (fallback aritmético): {boletas}")
            else:
                boletas = []

        print(f"Boletas obtenidas desde SP ({len(boletas)}): {boletas}")

    except Exception as e:
        print(f"Error obteniendo boletas: {e}")
        boletas = []

    try:
        edades = set(
            fila["Grupo_Edad"]
            for fila in filas
            if fila.get("Grupo_Edad")
        )
        print(f"Edades únicas sin ordenar: {edades}")

        edades_ordenadas = sorted(edades, key=valor_orden_edad)

        print(f"Edades únicas encontradas: {edades_ordenadas}")

    except Exception as e:

        print(f"Error procesando edades: {e}")
        edades_ordenadas = []
   
   # print(f"Contexto final: {contexto}")                
    return templates.TemplateResponse(
            "titulados_consulta.html", 
            {"request": request,
             "rechazo_info" : rechazo_info,
             "nombre_usuario": sess.nombre_completo,
             "periodo_default_literal": periodo_default_literal,
             "periodo_anterior_literal": periodo_anterior_literal,
             "periodos" : periodos,
             "niveles" : nombres_niveles,
             "niveles_por_unidad" : niveles_por_unidad,
             "unidades": resultado,
             "unidad_academica" : unidad_academica_usuario,
             "sigla_unidad_academica" : sigla_unidad_academica,
             "nombre_rol": nombre_rol,
             "session": sess,
             "nivel_acceso" : nivel,
             "nombre_nivel" : nombre_nivel,
             "contexto": contexto,
             "boletas": boletas,
             "filas": filas,
             "edades" : edades_ordenadas,
             "turnos": turnos_sp,
             "programa_modalidad_turnos_json": programa_modalidad_turnos_json,
             "programa_modalidad_boletas_json": programa_modalidad_boletas_json,
             "es_capturista": es_capturista,
             "es_validador": es_validador,
             "es_rol_superior": es_rol_superior,
             "es_rol_director": es_rol_director,
             "matricula_rechazada": matricula_rechazada,
             "acceso_restringido" : False,
             "session": sess}
             )

@router.post("/guardar-avance-titulados", response_class=JSONResponse)
def guardar_titulados(
    datos: List[dict],
    sess = Depends(get_current_session),
    db: Session = Depends(get_db)):

    id_rol = int(getattr(sess, 'id_rol', 0) or 0)
    if id_rol != 3:
        return JSONResponse(
            content={"status": "error", "message": "Acceso denegado: Solo el rol capturista tiene permisos para guardar datos."},
            status_code=403
        )

    try:
        verificar_permiso_formato(db, int(sess.id_usuario), 4, id_rol=id_rol)
    except HTTPException as e:
        return JSONResponse(content={"status": "error", "message": e.detail}, status_code=403)

    sigla_unidad_academica = sess.sigla_unidad_academica
    nivel = sess.nombre_nivel

    try:
        id_p, periodo = get_periodo_anterior_al_ultimo(db)
        id_p_actual, periodo_actual = get_periodo_activo(db)

        if periodo is None:
            return JSONResponse(
                content={"status": "error", "message": "No se encontró un periodo activo."}, 
                status_code=404
            )
    
    except Exception as e:
        print(f"Error al obtener periodo activo: {str(e)}")
        return JSONResponse(content={"status": "error", "message": f"Error al obtener periodo activo: {str(e)}"}, status_code=500)

    print(f"Datos recibidos para guardar: {datos}")

    try:
        registros = preparar_datos_temp_titulados(
            datos=datos,
            periodo = periodo,
            sigla= sigla_unidad_academica,
            nivel= nivel
        )

       # print(f"Registros preparados para guardar: {registros}")

        total = insertar_temp_titulados(db, registros)

        #insertar en titulados

        insertar_titulados_sp(db, sigla_unidad_academica, sess.usuario, host, periodo_actual, nivel)
 
    except Exception as e:
        print(f"Error preparando datos para guardar: {e}")
        return JSONResponse(content={"status": "error", "message": f"Error preparando datos: {str(e)}"}, status_code=500)
    
    return {"status": "guardado", "total_registros": total}


@router.post("/finalizar-titulados", response_class=JSONResponse)
def finalizar_captura_titulados(
    payload: FinalizarTituladosRequest,
    sess=Depends(get_current_session),
    db: Session = Depends(get_db)
):
    id_rol = int(getattr(sess, 'id_rol', 0) or 0)
    if id_rol != 3:
        return JSONResponse(
            content={"status": "error", "message": "Acceso denegado: Solo el rol capturista tiene permisos para finalizar captura."},
            status_code=403
        )

    try:
        verificar_permiso_formato(db, int(sess.id_usuario), 4, id_rol=id_rol)
    except HTTPException as e:
        return JSONResponse(content={"status": "error", "message": e.detail}, status_code=403)

    datos     = payload.datos
    programa  = payload.programa
    modalidad = payload.modalidad
    sigla     = sess.sigla_unidad_academica
    nivel     = sess.nombre_nivel

    try:
        id_p,        periodo        = get_periodo_anterior_al_ultimo(db)
        id_p_actual, periodo_actual = get_periodo_activo(db)
        if periodo is None or periodo_actual is None:
            return JSONResponse(
                content={"status": "error", "message": "No se encontró un periodo activo."},
                status_code=404
            )
    except Exception as e:
        return JSONResponse(
            content={"status": "error", "message": f"Error al obtener periodo activo: {str(e)}"},
            status_code=500
        )

    # Preparar registros fuera de cualquier condición para que siempre exista la variable
    registros = []
    if datos:
        try:
            if payload.origen == "db":
                registros = preparar_datos_temp_titulados_desde_db(
                    datos=datos,
                    periodo=periodo,
                    sigla=sigla,
                    nivel=nivel
                )
            else:
                registros = preparar_datos_temp_titulados(
                    datos=datos,
                    periodo=periodo,
                    sigla=sigla,
                    nivel=nivel
                )
        except Exception as e:
            return JSONResponse(
                content={"status": "error", "message": f"Error al preparar datos: {str(e)}"},
                status_code=500
            )

    # -------------------------------------------------------------------------
    # SEMILLA EN '0': Si no hay datos del frontend, consultar el SP para obtener
    # la estructura de filas del programa+modalidad y sembrar Temp_Titulados con
    # Titulados=0. Esto permite finalizar directamente aunque no haya alumnos
    # (igual que en el módulo de Egresados).
    # -------------------------------------------------------------------------
    if not registros:
        try:
            print(f"[finalizar-titulados] Sin datos del frontend → consultando SP para sembrar con 0s "
                  f"(programa={programa}, modalidad={modalidad}, sigla={sigla}, nivel={nivel})")

            # 1. Revisar si ya existen filas en Temp_Titulados para esta combinación
            temp_existente = db.query(Temp_Titulados).filter(
                Temp_Titulados.Sigla == sigla,
                Temp_Titulados.Periodo == periodo,
                Temp_Titulados.Nivel == nivel,
                Temp_Titulados.Nombre_Programa == programa,
                Temp_Titulados.Modalidad == modalidad,
            ).all()

            if temp_existente:
                print(f"[finalizar-titulados] Temp_Titulados ya tiene {len(temp_existente)} filas; "
                      f"se usarán tal cual (no se sobreescriben con 0s).")
            else:
                # 2. Consultar el SP para obtener la estructura de filas
                filas_sp = get_titulados(
                    db=db,
                    unidad_academica=sigla,
                    periodo=periodo_actual,
                    nivel=nivel,
                    usuario=sess.usuario or "sistema",
                    host=host,
                )

                # Filtrar solo el programa+modalidad que se está finalizando
                filas_sp_filtradas = [
                    f for f in filas_sp
                    if str(f.get("Nombre_Programa", "")).strip() == str(programa).strip()
                    and str(f.get("Modalidad", "")).strip() == str(modalidad).strip()
                ]

                print(f"[finalizar-titulados] Filas SP filtradas para {programa}/{modalidad}: "
                      f"{len(filas_sp_filtradas)}")

                if filas_sp_filtradas:
                    # Crear registros con los datos estructurales del SP y Titulados=0
                    registros_cero = [
                        Temp_Titulados(
                            Periodo=periodo,
                            Sigla=sigla,
                            Nombre_Programa=str(f.get("Nombre_Programa", "") or ""),
                            Nombre_Rama=str(f.get("Nombre_Rama", "") or ""),
                            Nivel=str(f.get("Nivel", nivel) or nivel),
                            Modalidad=str(f.get("Modalidad", "") or ""),
                            Grupo_Edad=str(f.get("Grupo_Edad", "") or ""),
                            Boleta=int(f["Boleta"]) if str(f.get("Boleta", "")).strip().lstrip("-").isdigit() else 0,
                            Tipo_Titulacion=str(f.get("Tipo_Titulacion", "") or ""),
                            Turno=str(f.get("Turno", "") or ""),
                            Sexo=str(f.get("Sexo", "") or ""),
                            Titulados=0,
                        )
                        for f in filas_sp_filtradas
                    ]
                    insertar_temp_titulados(db, registros_cero)
                    print(f"[finalizar-titulados] Sembradas {len(registros_cero)} filas con Titulados=0 en Temp_Titulados.")
                else:
                    # 3. SP tampoco devuelve filas → crear un registro mínimo con 0s
                    # para que el SP de finalización pueda procesar la combinación
                    print(f"[finalizar-titulados] SP sin filas para {programa}/{modalidad}; "
                          f"creando registros mínimos con Titulados=0.")
                    registros_minimo = [
                        Temp_Titulados(
                            Periodo=periodo,
                            Sigla=sigla,
                            Nombre_Programa=str(programa),
                            Nombre_Rama="",
                            Nivel=str(nivel),
                            Modalidad=str(modalidad),
                            Grupo_Edad="",
                            Boleta=0,
                            Tipo_Titulacion="",
                            Turno=turno,
                            Sexo=sexo,
                            Titulados=0,
                        )
                        for turno in ["Matutino", "Vespertino"]
                        for sexo in ["Hombre", "Mujer"]
                    ]
                    insertar_temp_titulados(db, registros_minimo)
                    print(f"[finalizar-titulados] Sembrados {len(registros_minimo)} registros mínimos con Titulados=0.")

        except Exception as e_semilla:
            traceback.print_exc()
            print(f"[finalizar-titulados] ⚠️ No se pudo sembrar Temp_Titulados con 0s: {str(e_semilla)}")
            # No bloqueamos: intentamos continuar con la finalización de todas formas

    try:
        # 1. Insertar en Temp_Titulados si hay registros del frontend
        if registros:
            insertar_temp_titulados(db, registros)

        # 2. SP programa-modalidad (borra Temp_Titulados al terminar)
        finalizar_captura_programa_modalidad(
            db, periodo_actual, sigla,
            modalidad, programa, sess.usuario, host, nivel
        )

        # 3. Verificar si todos los programas-modalidad de la UA están en semáforo 3
        # REGLA: Los SPs se ejecutan con periodo_actual (ellos hacen -1 internamente),
        # pero los semáforos quedan escritos en 'periodo' (el anterior al activo).
        # → La consulta de semáforos en BD debe hacerse con 'periodo' (el anterior).
        todos_finalizados = verificar_todos_programas_finalizados(
            db, periodo, sigla, nivel
        )

        print(f"[finalizar-titulados] todos_finalizados={todos_finalizados} "
              f"(verificando semáforos en periodo='{periodo}' [anterior], sigla='{sigla}', nivel='{nivel}')")

        # 4. Si todos están en 3, reinsertar y ejecutar SP de unidad académica
        if todos_finalizados:
            # SP_Finaliza_Captura_Titulados actualiza Semaforo_UA mediante un JOIN con
            # Temp_Titulados. El SP anterior (SP_Actualiza_Titulados_Por_Semestre_AU) ya
            # borró esa tabla, por lo que debemos sembrar al menos un registro antes de
            # llamar al SP de finalización.
            # IMPORTANTE: este SP NO hace periodo-1 internamente → recibe 'periodo' (anterior).
            if registros:
                db.expunge_all()
                insertar_temp_titulados(db, registros)
            else:
                # Temp_Titulados fue borrada por el SP anterior; insertar registro mínimo
                # con 'periodo' (anterior) para que el JOIN del SP funcione.
                registro_seed = Temp_Titulados(
                    Periodo=periodo,       # ← periodo ANTERIOR, donde están los datos
                    Sigla=sigla,
                    Nombre_Programa=programa,
                    Nombre_Rama="",
                    Nivel=nivel,
                    Modalidad=modalidad,
                    Grupo_Edad="",
                    Boleta=0,
                    Tipo_Titulacion="",
                    Turno="Matutino",
                    Sexo="Hombre",
                    Titulados=0,
                )
                insertar_temp_titulados(db, [registro_seed])
                print(f"[finalizar-titulados] Registro mínimo sembrado en Temp_Titulados "
                      f"(periodo='{periodo}', sigla='{sigla}', nivel='{nivel}') "
                      f"para que SP_Finaliza_Captura_Titulados pueda actualizar Semaforo_UA.")

            # SP_Finaliza_Captura_Titulados NO hace periodo-1 internamente →
            # recibe 'periodo' (el anterior) para coincidir con lo que hay en Temp_Titulados.
            finalizar_unidad_academica(
                db, periodo, sigla, modalidad, programa,
                sess.usuario, host, nivel
            )
            print(f"[finalizar-titulados] SP_Finaliza_Captura_Titulados ejecutado para "
                  f"sigla='{sigla}', periodo='{periodo}' [anterior], nivel='{nivel}'")

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            content={"status": "error", "message": f"Error al finalizar captura: {str(e)}"},
            status_code=500
        )

    return JSONResponse(
        content={
            "status": "finalizado",
            "unidad_finalizada": todos_finalizados
        }
    )


validar_acuse = VerificarAccesoAcuse()

@router.get('/acuse-validacion')
async def acuse_titulados_view(
    request: Request,
    periodo: str,
    nivel: str,
    unidad: str,
    sess = Depends(validar_acuse),
    db: Session = Depends(get_db),
    exportando_pdf: bool = False
):
    
    try:
        id_periodo_req = db.query(Periodo.Id_Periodo).filter(Periodo.Periodo == periodo).scalar()

        if not id_periodo_req:
            return JSONResponse(
                content={"status": "error", "message": "No se encontró el periodo especificado."}, 
                status_code=404
            )
    
    except Exception as e:
        print(f"Error al obtener periodo: {str(e)}")
        return JSONResponse(content={"status": "error", "message": f"Error al obtener periodo: {str(e)}"}, status_code=500)

    
    print(f"Generando acuse para Unidad: {unidad}, Periodo: {periodo}, Nivel: {nivel}, Usuario: {sess.usuario}, Host: {host}")



    # El SP requiere siempre el periodo actual para funcionar correctamente
    id_p_actual, periodo_actual = get_periodo_activo(db)
    periodo_sp = periodo_actual or periodo

    contexto_sp, filas = obtener_titulados(db, unidad, periodo_sp, nivel, sess.usuario, host)
    

    #print (f"Contexto SP: {contexto_sp}")
    #print (f"Filas SP: {filas}")

    tablas = procesar_titulados(filas)

    print ("Muchas tablas")

    id_rol = int(sess.id_rol)
    Id_Unidad_Academica = db.query(Unidad_Academica.Id_Unidad_Academica).filter(
        Unidad_Academica.Sigla == unidad,
        Unidad_Academica.Id_Estatus == 1
    ).scalar()

    print("ID unidad academica", Id_Unidad_Academica)

    id_nivel = db.query(Nivel.Id_Nivel).filter(Nivel.Nivel == nivel).scalar()

    print("Nivel id:", id_nivel)

    # Obtenemos encargados filtrando por formato 4 (Titulados) para que el capturista
    # corresponda al usuario con permiso asignado en Formato_Usuario para este formato,
    # filtrando además por nivel para no mezclar capturistas de distintos niveles.
    encargados = obtener_encargados(db, Id_Unidad_Academica, 4, id_nivel)

    nombre_capturista = encargados["nombre_capturista"]
    nombre_ceget      = encargados["nombre_ceget"]
    nombre_titular    = encargados["nombre_titular"]

    print("Encargados Obtenidos : ", encargados)
    print("EK* id:", id_periodo_req)
    
    # El semáforo de Titulados se almacena en el penúltimo periodo (anterior al último),
    # igual que en Egresados, ya que los SPs buscan internamente periodo_activo - 1
    id_p_anterior, _ = get_periodo_anterior_al_ultimo(db)
    id_semaforo_periodo = id_p_anterior or id_p_actual  # fallback al activo si no hay anterior

    print(f"[acuse] Buscando semáforo en periodo anterior id={id_p_anterior} (activo={id_p_actual})")

    semaforo_captura = db.query(SemaforoUnidadAcademica).filter(
        SemaforoUnidadAcademica.Id_Periodo == id_semaforo_periodo,
        SemaforoUnidadAcademica.Id_Unidad_Academica == Id_Unidad_Academica,
        SemaforoUnidadAcademica.Id_Formato == 4,
        SemaforoUnidadAcademica.Id_Nivel == id_nivel
    ).first()

    # Fallback: si no hay en el anterior, intentar en el activo
    if not semaforo_captura and id_semaforo_periodo != id_p_actual:
        semaforo_captura = db.query(SemaforoUnidadAcademica).filter(
            SemaforoUnidadAcademica.Id_Periodo == id_p_actual,
            SemaforoUnidadAcademica.Id_Unidad_Academica == Id_Unidad_Academica,
            SemaforoUnidadAcademica.Id_Formato == 4,
            SemaforoUnidadAcademica.Id_Nivel == id_nivel
        ).first()
        if semaforo_captura:
            print(f"[acuse] Semáforo encontrado en fallback (periodo activo id={id_p_actual})")
    
    print("Semaforo Captura:", semaforo_captura)

    semaforo = 0

    if semaforo_captura:
        semaforo = semaforo_captura.Id_Semaforo
        print("Semaforo:",semaforo)
    
    print("Semaforo:", semaforo)

    no_validado = semaforo < 9


    puede_validar = False
    usuario_ya_valido = False
    usuario_ya_rechazo = False
    pendiente_validacion = False
    esperando_por_rol = "Capturista"

    if semaforo is not None and semaforo > 0:
        if semaforo in [1, 2]:
            esperando_por_rol = "Capturista"
        elif semaforo < 9:
            semaforo_a_siguiente_rol = {
                3: 4,  # Semáforo 3 -> Sigue CEGET (4)
                4: 5,  # Semáforo 4 -> Sigue Titular UA (5)
                5: 6,  # Semáforo 5 -> Sigue Analista (6)
                6: 7,  # Semáforo 6 -> Sigue Jefe/a de Departamento (7)
                7: 8,  # Semáforo 7 -> Sigue Jefe/a de División (8)
                8: 9,  # Semáforo 8 -> Sigue Director/a de DII (9)
            }
            try:
                siguiente_rol_id = semaforo_a_siguiente_rol.get(semaforo, int(semaforo) + 1)
                rol_obj = db.query(CatRoles).filter(CatRoles.Id_Rol == siguiente_rol_id).first()
                esperando_por_rol = rol_obj.Rol if rol_obj else "Capturista"
            except Exception:
                esperando_por_rol = "Capturista"
        else:
            esperando_por_rol = None

    try:
        if id_rol in [4, 5, 6, 7, 8, 9] and id_periodo_req is not None:
            estado_semaforo = semaforo
            print()
            print()
            print(f"Estado del semáforo para la unidad {unidad} en el periodo {id_periodo_req}: {semaforo}")
            # Regla de jerarquía real (alineada a los SPs de Validar/Rechazar):
            # SP_Valida_Titulados y SP_Rechaza_Titulados validan que:
            #   sua.Id_Semaforo == (Id_Rol del usuario) - 1
            # Esto permite pasos distintos para 6,7,8,9 en vez de agruparlos.
            semaforo_esperado = id_rol - 1

            if semaforo is not None:
                if semaforo == semaforo_esperado:
                    puede_validar = True
                    usuario_ya_valido = False
                    usuario_ya_rechazo = False
                elif semaforo > semaforo_esperado:
                    usuario_ya_valido = True
                else:
                    # Aún no toca este nivel
                    puede_validar = False

            try:
                id_usuario_actual = int(sess.id_usuario)
                rechazo_usuario = db.query(Validacion).filter(
                    Validacion.Id_Periodo == id_semaforo_periodo,
                    Validacion.Id_Usuario == id_usuario_actual,
                    Validacion.Id_Formato == 4,
                    Validacion.Validado == 0
                ).first()
                if rechazo_usuario:
                    if not puede_validar:
                        usuario_ya_rechazo = True
            except Exception:
                # Si algo falla aquí, no bloqueamos por seguridad de UI
                pass

            if not puede_validar and not usuario_ya_valido and not usuario_ya_rechazo and semaforo > 0:
                pendiente_validacion = True
    except Exception as ex:
        print(f"[acuse titulados] Error en lógica de validación: {ex}")
        # Si algo falla, solo no mostramos estado (UI seguirá normal)
        pass



    fecha_hoy = datetime.now().strftime("%d/%m/%Y")

    return templates.TemplateResponse("titulados_acuse.html", {
        "request"       : request,
        "periodo"       : contexto_sp.get("Periodo") or periodo,
        "unidad"        : contexto_sp.get("Sigla") or unidad,
        "nivel"         : nivel,
        "exportando_pdf": exportando_pdf,
        "fecha_hoy"     : fecha_hoy,
        "nombre_capturista" : nombre_capturista,
        "nombre_ceget"  : nombre_ceget,
        "nombre_titular": nombre_titular,
        "no_validado"   : no_validado,
        "id_rol"        : id_rol,
        "id_unidad_academica": Id_Unidad_Academica,
        "id_nivel"      : id_nivel,
        "puede_validar" : puede_validar,
        "usuario_ya_valido" : usuario_ya_valido,
        "usuario_ya_rechazo": usuario_ya_rechazo,
        "esperando_por_rol": esperando_por_rol,
        "pendiente_validacion": pendiente_validacion,
        "estado_semaforo_actual": semaforo,
        "session": sess,
        **tablas
           # desempaca todas las tablas directamente
    })

@router.get('/acuse-validacion/pdf')
async def acuse_titulados_pdf(
    request: Request,
    periodo: str,
    nivel: str,
    unidad: str,
    sess=Depends(validar_acuse),
    db: Session = Depends(get_db)
):
    try:
        import weasyprint
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=f"WeasyPrint no está instalado: {exc}")

    resp = await acuse_titulados_view(request, periodo, nivel, unidad, sess, db, exportando_pdf=True)

    if isinstance(resp, JSONResponse):
        # Tu vista devuelve JSONResponse en caso de error (p. ej. periodo no encontrado)
        return resp

    if isinstance(resp.body, memoryview):
        html_text = resp.body.tobytes().decode('utf-8')
    else:
        html_text = bytes(resp.body).decode('utf-8')

    base_path = Path(__file__).resolve().parents[2] / 'frontend' / 'static'
    ruta_css = base_path / 'css' / 'components' / 'matricula_acuse.css'

    if not ruta_css.exists():
        ruta_css = base_path / 'css' / 'components' / 'egresados_acuse.css'

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

    filename = f"acuse_titulados_{unidad}_{periodo}.pdf".replace(' ', '_')
    
    return Response(
        content=pdf_bytes,
        media_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )


@router.get('/exportar-excel-titulados')
async def exportar_titulados_excel(
    request: Request,
    periodo: str,
    nivel: str,
    unidad: str,
    sess=Depends(validar_acuse),
    db: Session = Depends(get_db)
):
    """
    Exporta a Excel los datos de SP_Consulta_Titulados_Unidad_Academica.
    Filtra ÚNICAMENTE aquellos registros que tengan en la columna de Titulados > 0 (omitiendo los '0').
    """
    import io
    import xlsxwriter
    from fastapi.responses import StreamingResponse

    usuario_login = sess.usuario
    host = "Sistema"

    # Resolver sigla limpia
    ua_sigla = (unidad or sess.sigla_unidad_academica or '').strip()
    if ua_sigla:
        ua_obj = db.query(Unidad_Academica).filter(
            (Unidad_Academica.Sigla == ua_sigla) | (Unidad_Academica.Nombre == ua_sigla)
        ).first()
        if ua_obj and ua_obj.Sigla:
            ua_sigla = ua_obj.Sigla

    # 1. Determinar el periodo de consulta adecuado de forma directa (igual que hace acuse_titulados_view)
    id_p_actual, periodo_actual = get_periodo_activo(db)
    periodo_a_usar = periodo_actual or periodo

    datos_titulados = get_titulados(
        db=db,
        unidad_academica=ua_sigla,
        periodo=periodo_a_usar,
        nivel=nivel,
        usuario=usuario_login,
        host=host
    )

    def extraer_titulados_filtrados(datos):
        filtrados = []
        for row in datos:
            val = row.get('Titulados')
            if val is None:
                for k, v in row.items():
                    if str(k).lower() == 'titulados':
                        val = v
                        break
            try:
                num = int(float(val)) if val not in (None, '') else 0
            except (ValueError, TypeError):
                num = 0
            if num > 0:
                filtrados.append(row)
        return filtrados

    rows_filtradas = extraer_titulados_filtrados(datos_titulados)

    # 2. Fallback solo si no se encontraron registros con periodo_a_usar
    if not rows_filtradas and periodo and periodo != periodo_a_usar:
        datos_alterno = get_titulados(
            db=db,
            unidad_academica=ua_sigla,
            periodo=periodo,
            nivel=nivel,
            usuario=usuario_login,
            host=host
        )
        rows_filtradas = extraer_titulados_filtrados(datos_alterno)

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    ws = workbook.add_worksheet("Titulados")

    if rows_filtradas:
        headers = [k for k in rows_filtradas[0].keys() if str(k).lower() not in ('id_semaforo', 'id_semaforo_actual')]
        header_format = workbook.add_format({'bold': True, 'bg_color': '#750946', 'font_color': '#FFFFFF'})
        for col, h in enumerate(headers):
            ws.write(0, col, h, header_format)
        for row_idx, row in enumerate(rows_filtradas, start=1):
            for col_idx, key in enumerate(headers):
                ws.write(row_idx, col_idx, row.get(key, ''))
    else:
        ws.write(0, 0, "No hay datos de titulados mayores a 0 para los filtros seleccionados")

    workbook.close()
    output.seek(0)

    unidad_limpia = str(ua_sigla).replace(' ', '_').strip()
    periodo_limpio = str(periodo).replace('/', '_').replace(' ', '_').strip()
    nivel_limpio = str(nivel).replace(' ', '_').strip()
    filename = f"Titulados_{unidad_limpia}_{nivel_limpio}_{periodo_limpio}.xlsx"

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.post('/validar')
async def validar_titulados(request: Request, sess=Depends(get_current_session), db: Session = Depends(get_db)):
    """
    Valida los datos de Titulados.
    Ejecuta el SP [dbo].[SP_Valida_Titulados] (Formato 4) para avanzar semáforo y registrar en Validacion.
    """

    print("Se esta validando titulados")
    try:
        # NOTA: Evitamos hacer await request.json() dos veces seguidas para no congelar la petición
        body = await request.json()
        
        # 1. Valores reales enviados desde la interfaz HTML/JS
        periodo_in = body.get("periodo")
        unidad_in = body.get("unidad")    # 👈 El nombre/sigla de la escuela que estás viendo
        nivel_in = body.get("nivel")      # 👈 El nivel que estás viendo

        print(f"Datos recibidos para validación: periodo={periodo_in}, unidad={unidad_in}, nivel={nivel_in}")

        nota_in = (body.get('nota') or '').strip()

        # Datos de la sesión del usuario que da click
        id_rol = int(sess.id_rol)
        usuario_sp = sess.usuario or 'sistema'
        _,periodo_literal = get_periodo_activo(db)
        host_sp = get_request_host(request)

        # Roles permitidos
        if id_rol not in [4, 5, 6, 7, 8, 9]:
            return JSONResponse(content={"success": False, "message": "Solo roles de validación pueden ejecutar esta acción."}, status_code=403)

        if periodo_in is None:
            return JSONResponse(content={"success": False, "message": "No se recibió el periodo."}, status_code=400)

        # Verificación de seguridad IDOR para roles de escuela (4 = CEGET, 5 = Director)
        if id_rol in [4, 5]:
            sigla_sess = (sess.sigla_unidad_academica or '').strip().lower()
            target_ua = (unidad_in or '').strip().lower()
            if target_ua and sigla_sess and target_ua != sigla_sess:
                usuario_str = f"{sess.usuario} (ID:{sess.id_usuario})"
                print(f"[seguridad-IDOR] Intento no autorizado al validar Titulados. Usuario {usuario_str} intentó validar UA {unidad_in} (Asignada: {sigla_sess})")
                try:
                    registrar_bloqueo_seguridad(
                        request=request,
                        usuario_objetivo=usuario_str,
                        tipo_incidente="IDOR_ACCESO_NO_AUTORIZADO",
                        accion_tomada="ACCESO_DENEGADO_HTTP_403",
                        endpoint=f"/titulados/validar (UA: {unidad_in} vs Asignada: {sigla_sess})"
                    )
                except Exception:
                    pass
                return JSONResponse(
                    content={"success": False, "message": "Acceso denegado: No tienes permisos para validar otra Unidad Académica."},
                    status_code=403
                )



        # 2. STRATEGY FALLBACK: Priorizar lo que viene de la pantalla, si no, usar sesión
        unidad_sigla = (unidad_in or sess.sigla_unidad_academica or '').strip()
        if not unidad_sigla and hasattr(sess, 'id_unidad_academica'):
            try:
                ua = db.query(Unidad_Academica).filter(Unidad_Academica.Id_Unidad_Academica == int(sess.id_unidad_academica)).first()
                unidad_sigla = ua.Sigla if ua else ''
            except Exception:
                unidad_sigla = ''

        if not unidad_sigla:
            return {"success": False, "message": "No se pudo resolver la Unidad Académica."}

        nivel_literal = (nivel_in or sess.nombre_nivel or '').strip()
        if not nivel_literal and hasattr(sess, 'id_nivel'):
            nivel_literal = str(sess.id_nivel)

        nota_sp = nota_in or f"Validado por {sess.nombre_completo}"

        # Intentar obtener semáforo para monitoreo
        try:
            periodo_id_db , _ = get_periodo_anterior_al_ultimo(db)
            sem = db.query(SemaforoUnidadAcademica).filter(
                SemaforoUnidadAcademica.Id_Periodo == periodo_id_db,
                SemaforoUnidadAcademica.Id_Unidad_Academica == int(sess.id_unidad_academica),
                SemaforoUnidadAcademica.Id_Formato == 4,
            ).first()
            sem_actual = sem.Id_Semaforo if sem else None
        except Exception:
            sem_actual = None

        # 🔍 IMPRESIÓN DETALLADA ANTES DE EXECUTAR EL SP
        print(f"\n {'='*60}")
        print("📊 PREPARANDO EJECUCIÓN DE STORED PROCEDURE")
        print(f"{'='*60}")
        print(f" SQL: EXEC [dbo].[SP_Valida_Titulados]")
        print(f" 🔹 @PPeriodo          = '{periodo_literal}' (Origen: {periodo_in})")
        print(f" 🔹 @UUnidad_Academica = '{unidad_sigla}' (Origen JS: '{unidad_in}' | Sess: '{sess.sigla_unidad_academica}')")
        print(f" 🔹 @NNivel            = '{nivel_literal}' (Origen JS: '{nivel_in}' | Sess: '{sess.nombre_nivel}')")
        print(f" 🔹 @uusuario          = '{usuario_sp}'")
        print(f" 🔹 @HHost             = '{host_sp}'")
        print(f" 🔹 @NNota             = '{nota_sp}'")
        print(f" [DEBUG] Semáforo actual ID en DB: {sem_actual}")
        print(f"{'='*60}\n")

        sql = text("""
            SET NOCOUNT ON;
            EXEC [dbo].[SP_Valida_Titulados]
                @PPeriodo = :periodo,
                @UUnidad_Academica = :ua,
                @NNivel = :nivel,
                @uusuario = :usuario,
                @HHost = :host,
                @NNota = :nota
        """)

        # Ejecución
        result = db.execute(sql, {
            'periodo': periodo_literal,
            'ua': unidad_in,
            'nivel': nivel_in,
            'usuario': usuario_sp,
            'host': host_sp,
            'nota': nota_sp,
        })

        try:
            sp_rows = [dict(r) for r in result.mappings().all()]
        except Exception:
            sp_rows = []

        db.commit()
        print("✅ [DB] Commit ejecutado de forma exitosa.")

        # Enviar correo de acuse cuando el Titular (id_rol=5) valida Y todos los módulos de la UA ya están en semáforo >= 5
        acuse_info = None
        correo_acuse_enviado = False
        acuse_error = None
        correo_acuse_error = None

        if id_rol == 5:
            ua_obj = db.query(Unidad_Academica).filter(
                (Unidad_Academica.Sigla == unidad_in) | (Unidad_Academica.Nombre == unidad_in)
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

                    acuse_info, correo_acuse_enviado, acuse_error, correo_acuse_error = enviar_correo_acuse_titular(
                        db=db,
                        id_usuario=int(sess.id_usuario),
                        usuario_login=usuario_sp,
                        nombre_completo=str(sess.nombre_completo or usuario_sp),
                        unidad_sigla=unidad_in,
                        unidad_nombre=str(getattr(ua_obj, 'Nombre', '') or unidad_in),
                        clave_ur=str(getattr(ua_obj, 'Clave', '') or ''),
                        periodo_literal=periodo_literal,
                        estatus_entrega=estatus_entrega,
                    )
                except Exception as _e:
                    acuse_error = str(_e)
                    print(f"❌ Error inesperado al generar acuse titulados: {_e}")
            else:
                print(f"ℹ️ Titulados validados por Titular. Aún no se genera acuse porque faltan módulos por validar en la UA ({unidad_in}).")

        return {
            "success": True,
            "message": "Titulados validados correctamente",
            "correo_acuse_enviado": correo_acuse_enviado,
            "acuse": acuse_info,
            "acuse_error": acuse_error,
            "correo_acuse_error": correo_acuse_error,
        }

    except Exception as e:
        db.rollback()
        print(f"❌ Error crítico al validar Titulados: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/rechazar')
async def rechazar_titulados(request: Request, sess=Depends(get_current_session), db: Session = Depends(get_db)):
    """
    Rechaza los datos de Titulados.
    Ejecuta el SP [dbo].[SP_Rechaza_Titulados] (Formato 4) para regresar semáforo y registrar en Validacion.
    """
    try:
        data = await request.json()
        periodo_in = data.get('periodo')
        unidad_in = data.get('unidad')  
        nivel_in = data.get('nivel')    
        motivo = (data.get('motivo') or '').strip()

        periodo_in = data.get('periodo')
        motivo = (data.get('motivo') or '').strip()
        _,periodo_literal = get_periodo_activo(db)


        Id_Unidad_Academica = db.query(Unidad_Academica.Id_Unidad_Academica).filter(
            Unidad_Academica.Sigla == unidad_in,
            Unidad_Academica.Id_Estatus == 1
        ).scalar()

        id_nivel = db.query(Nivel.Id_Nivel).filter(Nivel.Nivel == nivel_in).scalar()  

        if not motivo:
            raise HTTPException(status_code=400, detail="Debe proporcionar un motivo de rechazo")

        # Respetar nvarchar(250)
        if len(motivo) > 250:
            motivo = motivo[:250]

        # Sesión
        id_rol = int(sess.id_rol)
        usuario_sp = sess.usuario or 'sistema'
       # unidad_sigla = (sess.sigla_unidad_academica or '').strip()
        nivel_literal = (sess.nombre_nivel or '').strip()
        host_sp = get_request_host(request)

        if id_rol not in [4, 5, 6, 7, 8, 9]:
            return JSONResponse(content={"success": False, "message": "Solo roles de validación pueden ejecutar esta acción."}, status_code=403)

        if periodo_in is None:
            return JSONResponse(content={"success": False, "message": "No se recibió el periodo."}, status_code=400)

        # Verificación de seguridad IDOR para roles de escuela (4 = CEGET, 5 = Director)
        if id_rol in [4, 5]:
            sigla_sess = (sess.sigla_unidad_academica or '').strip().lower()
            target_ua = (unidad_in or '').strip().lower()
            if target_ua and sigla_sess and target_ua != sigla_sess:
                usuario_str = f"{sess.usuario} (ID:{sess.id_usuario})"
                print(f"[seguridad-IDOR] Intento no autorizado al rechazar Titulados. Usuario {usuario_str} intentó rechazar UA {unidad_in} (Asignada: {sigla_sess})")
                try:
                    registrar_bloqueo_seguridad(
                        request=request,
                        usuario_objetivo=usuario_str,
                        tipo_incidente="IDOR_ACCESO_NO_AUTORIZADO",
                        accion_tomada="ACCESO_DENEGADO_HTTP_403",
                        endpoint=f"/titulados/rechazar (UA: {unidad_in} vs Asignada: {sigla_sess})"
                    )
                except Exception:
                    pass
                return JSONResponse(
                    content={"success": False, "message": "Acceso denegado: No tienes permisos para rechazar otra Unidad Académica."},
                    status_code=403
                )

        if not nivel_literal:
            nivel_literal = str(sess.id_nivel)

        print(f"\n{'='*60}")
        print("🔴 RECHAZAR TITULADOS (SP_Rechaza_Titulados)")
        print(f"Usuario: {usuario_sp} | Rol: {id_rol}")
        print(f"Periodo: {periodo_literal} | UA: {unidad_in} | Nivel: {nivel_in} | Id_nivel: {id_nivel} | Id_UA: {Id_Unidad_Academica}")
        print(f"Host: {host_sp}")
        print(f"Motivo: {motivo}")
        print(f"{'='*60}\n")

        sql = text("""
            EXEC [dbo].[SP_Rechaza_Titulados]
                @PPeriodo = :periodo,
                @UUnidad_Academica = :ua,
                @NNivel = :nivel,
                @UUsuario = :usuario,
                @HHost = :host,
                @NNota = :nota
        """)

        db.execute(sql, {
            'periodo': periodo_literal,
            'ua': unidad_in,
            'nivel': nivel_in,
            'usuario': usuario_sp,
            'host': host_sp,
            'nota': motivo,
        })
        
        correos = obtener_correos_involucrados(
            db=db,
            id_unidad= Id_Unidad_Academica,
            id_formato=4
        )

        print("Estos son los correos", correos)

        notificar_rechazo_global(
            modulo_rechazado="Titulados", 
            id_rol_que_rechaza= id_rol,
            correos= correos,
            unidad_academica=unidad_in,
        )

        db.commit()

        return {"success": True, "message": "Titulados rechazados. Se notificará al capturista."}
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error al rechazar Titulados: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
