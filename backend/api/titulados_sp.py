from typing import List
from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from backend.api import unidad_academica
from backend.database.connection import get_db
from backend.core.templates import templates
from backend.schemas import Nivel
from backend.services.titulados_service import obtener_titulados, preparar_datos_temp_titulados
from backend.crud.ConsultaTitulados import insertar_temp_titulados, insertar_titulados_sp
from backend.services.periodo_service import get_periodo_activo, get_periodo_anterior_al_ultimo, get_ultimo_periodo
from backend.core.auth import get_current_session
from backend.database.models.Temp_Titulados import Temp_Titulados as TituladosModel
from backend.database.models.CatUnidadAcademica import CatUnidadAcademica as Unidad_Academica

host = "Test"

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

@router.get("/consulta", response_class=HTMLResponse)

@router.get("/consulta", response_class=HTMLResponse)
async def consulta_titulados(
    request: Request,
    sess = Depends(get_current_session),
    db: Session = Depends(get_db)
):
    
    contexto = {}
    filas = []
   
    id_rol = int(sess.id_rol)
    nombre_rol = sess.nombre_rol
    
    nombre = sess.nombre_usuario
    apellidoP_usuario = sess.apellidoP_usuario
    apellidoM_usuario = sess.apellidoM_usuario
    
    nombre_usuario = " ".join(filter(None, [nombre, apellidoP_usuario, apellidoM_usuario]))
    sigla_unidad_academica = sess.sigla_unidad_academica
    id_unidad_academica = int(sess.id_unidad_academica)
    nombre_nivel = sess.nombre_nivel


    if id_unidad_academica > 0:
            ua_usuario = db.query(Unidad_Academica).filter(
                Unidad_Academica.Id_Unidad_Academica == id_unidad_academica
            ).first()

    unidad_academica_usuario = ua_usuario.Nombre
    nivel = sess.id_nivel

    print(unidad_academica_usuario)
    """
    unidad_academica = sess.unidad_academica
   
    nombre_nivel = getattr(sess, 'nombre_nivel', "Nivel de Prueba")
    nivel_acceso = getattr(sess, 'id_nivel', 0)
    usuario = getattr(sess, 'usuario', "usuario_prueba")"""

    print(f"Usuario: {nombre_usuario}, Rol: {nombre_rol} (ID: {id_rol}), Unidad Académica: {unidad_academica} ({sigla_unidad_academica}), Nivel: {nombre_nivel}, Host: {host}")
    try:
        periodo_id, periodo_literal = get_periodo_activo(db)
        if not periodo_id or not periodo_literal:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error_message": "No hay un periodo activo configurado en el sistema.",
                "redirect_url": "/mod_principal/"
            })
        
        periodo_default_literal = periodo_literal
        print(f" Periodo por defecto: {periodo_default_literal}")
    except Exception as e:
        print(f" Error al obtener periodo: {str(e)}")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_message": f"Error al cargar el periodo: {str(e)}",
            "redirect_url": "/mod_principal/"
        })

    roles_permitidos = [1, 3, 4, 5, 6, 7, 8, 9]  #1=Admin, 3=Capturista, 4-9=Roles de validación/rechazo
    if id_rol not in roles_permitidos:
        if id_rol != 0:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error_message": f"Acceso denegado: Su rol ({nombre_rol}) no tiene permisos para acceder a esta funcionalidad.",
                "redirect_url": "/mod_principal/"
            })
        else:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error_message": "Acceso denegado: No se ha identificado un rol válido. Por favor, inicie sesión.",
                "redirect_url": "/login/"
            })
    

    es_capturista = (id_rol == 3)
    es_validador = (id_rol in [4, 5, 6, 7, 8, 9])  
    es_rol_director = (id_rol in [4, 5])  
    es_rol_superior = (id_rol in [6, 7, 8, 9])  
    modo_vista = "captura" if es_capturista else "validacion"

    try:
        print(
            f"Obteniendo titulados para UA: {sigla_unidad_academica}, "
            f"Periodo: {periodo_default_literal}, "
            f"Nivel: {nombre_nivel}, "
            f"Usuario: {nombre_usuario}"
        )

        contexto, filas = obtener_titulados(
            db=db,
            unidad_academica=sigla_unidad_academica,
            periodo=periodo_default_literal,
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

    try:
        boleta = contexto.get("Boleta")

        if boleta:
            boleta = int(boleta)
            boletas = list(range(boleta + 1, boleta - 11, -1))

        print(f"Boletas obtenidas: {boletas}")

    except Exception as e:

        print(f"Error calculando boletas: {e}")
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
             "nombre_usuario": nombre_usuario,
             "periodo_default_literal": periodo_default_literal,
             "unidad_academica" : unidad_academica_usuario,
             "nombre_rol": nombre_rol,
             "nivel_acceso" : nivel,
             "contexto": contexto,
             "boletas": boletas,
             "filas": filas,
             "edades" : edades_ordenadas,
             "es_capturista": es_capturista,
             "acceso_restringido" : False}
             )

@router.post("/guardar-avance-titulados", response_class=JSONResponse)

def guardar_titulados(
    request: Request,
    datos: List[dict],
    sess = Depends(get_current_session),
    db: Session = Depends(get_db)):
    
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