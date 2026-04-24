from typing import List
from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from backend.api import unidad_academica
from backend.database.connection import get_db
from backend.core.templates import templates
from backend.schemas import Nivel
from backend.services.titulados_service import obtener_titulados, preparar_datos_temp_titulados
from backend.crud.ConsultaTitulados import insertar_temp_titulados
from backend.services.periodo_service import get_periodo_activo, get_ultimo_periodo
from backend.database.models.Temp_Titulados import Temp_Titulados as TituladosModel


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

async def consulta_titulados(
    request: Request,
    db: Session = Depends(get_db)
):
    
    contexto = {}
    filas = []
    
    # Identificar la vista para usuarios (Quitar los default ya que conecte a la base)
    id_rol = int(request.session.get("id_rol",0))
    nombre_rol = request.session.get("nombre_rol", "Capturista")
    nombre = request.session.get("nombre_usuario", "Prueba")
    apellidoP_usuario = request.session.get("apellidoP_usuario", "123")
    apellidoM_usuario = request.session.get("apellidoM_usuario", "456")
    nombre_usuario = " ".join(filter(None, [nombre, apellidoP_usuario, apellidoM_usuario]))
    
    unidad_academica = request.session.get("unidad_academica", "unidad_prueba")
    sigla_unidad_academica = request.session.get("sigla_unidad_academica", "UAP")
    nombre_nivel = request.session.get("nombre_nivel", "Nivel de Prueba")
    nivel_acceso = request.session.get("id_nivel")
    usuario = request.session.get("usuario", "usuario_prueba")

    host = "Test"

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
            f"Usuario: {usuario}"
        )

        contexto, filas = obtener_titulados(
            db=db,
            unidad_academica=sigla_unidad_academica,
            periodo=periodo_default_literal,
            nivel=nombre_nivel,
            usuario=usuario,
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
             "unidad_academica" : unidad_academica,
             "nombre_rol": nombre_rol,
             "nivel_acceso" : nivel_acceso,
             "contexto": contexto,
             "boletas": boletas,
             "filas": filas,
             "edades" : edades_ordenadas,
             "es_capturista": es_capturista,
             "acceso_restringido" : False}
             )

@router.post("/guardar-avance-titulados", response_class=JSONResponse)

def guardar_titulados(request: Request, datos: List[dict], db: Session = Depends(get_db)):
    
    sigla_unidad_academica = request.cookies.get("sigla_unidad_academica", "UAP")
    nombre_nivel = request.cookies.get("nombre_nivel", "Nivel de Prueba")

    
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
    #print(f"Datos recibidos para guardar: {datos}")

    try:
        registros = preparar_datos_temp_titulados(
            datos=datos,
            periodo=datos[0].get("periodo", "Periodo Desconocido"),
            sigla=datos[0].get("sigla_unidad_academica", "SIGLA_DESCONOCIDA"),
            rama=datos[0].get("rama", "Rama Desconocida"),
            nivel=datos[0].get("nivel", "Nivel Desconocido")
        )

       # print(f"Registros preparados para guardar: {registros}")

        total = insertar_temp_titulados(db, registros)

    except Exception as e:
        print(f"Error preparando datos para guardar: {e}")
        return JSONResponse(content={"status": "error", "message": f"Error preparando datos: {str(e)}"}, status_code=500)
    
    return {"status": "guardado", "total_registros": total}