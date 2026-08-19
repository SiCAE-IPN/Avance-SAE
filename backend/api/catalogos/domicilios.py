from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.database.connection import get_db
from backend.core.templates import templates
from backend.core.auth import get_current_session
from backend.services.periodo_service import get_ultimo_periodo, get_periodo_activo
from backend.utils.request import get_request_host

router = APIRouter()

# --- Funciones auxiliares para catálogos ---
def consultaRama(db: Session):
    try:
        query = text("""EXEC dbo.SP_Consulta_Catalogo_Rama""")
        resultado = db.execute(query)
        return [dict(row) for row in resultado.mappings().all()]
    except Exception as e:
        return {"error": str(e)}
    
def consultaEntidad(db: Session):
    try:
        query = text("""EXEC dbo.SP_Consulta_Catalogo_Entidad""")
        resultado = db.execute(query)
        return [dict(row) for row in resultado.mappings().all()]
    except Exception as e:
        return {"error": str(e)}

# --- Endpoints ---

@router.get("/domicilios", response_class=HTMLResponse)
def domicilios_view(
    request: Request, 
    sess=Depends(get_current_session),
    db: Session = Depends(get_db)
):
    """
    Vista para consultar los domicilios mediante un Stored Procedure.
    """

    HHost = get_request_host(request) 
    UUsuario = getattr(sess, 'usuario', '') or ''
    id_rol = int(sess.id_rol)
    Rol = str(sess.nombre_rol)

    if id_rol == 3:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_message": "No tienes permisos para acceder a este formato.", 
            "redirect_url": "/mod_principal/",
            "session": sess
        })
    
    # Obtener periodo dinámico
    _, PPeriodo = get_periodo_activo(db) or get_ultimo_periodo(db)
    if not PPeriodo:
        PPeriodo = ""

    try:
        query = text("""
            EXEC dbo.SP_Consulta_Catalogo_Unidad_Academica
                @UUsuario = :UUsuario,
                @HHost = :HHost,
                @PPeriodo = :PPeriodo
        """)
        resultado = db.execute(query, {
            "UUsuario": UUsuario,
            "HHost": HHost,
            "PPeriodo": PPeriodo
        })

        data = [dict(row) for row in resultado.mappings().all()]
        Rama = consultaRama(db)
        Entidad = consultaEntidad(db)

    except Exception as e:
        print("Error al ejecutar SP_Consulta_Catalogo_Unidad_Academica:", e)
        data, Rama, Entidad = [], [], []
        
    return templates.TemplateResponse(
        "catalogos/domicilios.html",
        {
            "request": request,
            "domicilios": data,
            "rol": Rol,
            "nombre_rol": Rol,
            "nombre_usuario": getattr(sess, 'nombre_completo', '') or getattr(sess, 'nombre_usuario', ''),
            "sigla_unidad_academica": getattr(sess, 'sigla_unidad_academica', ''),
            "periodo_literal": PPeriodo,
            "rama": Rama,
            "entidad": Entidad,
            "session": sess
        }
    )


@router.post("/registrarUA")
def registrar_ua(
    data: dict, 
    request: Request, 
    sess=Depends(get_current_session), 
    db: Session = Depends(get_db)
):
    id_rol = int(getattr(sess, 'id_rol', 0) or 0)
    if id_rol == 3:
        return {"status": "error", "msg": "No tienes permisos para realizar esta acción."}

    print("Datos recibidos en REGISTRAR:", data)
    try:
        # Obtener valores en tiempo de ejecución
        HHost = get_request_host(request) 
        _, PPeriodo = get_periodo_activo(db) or get_ultimo_periodo(db)
        PPeriodo = PPeriodo or ""
        UUsuario = getattr(sess, 'usuario', '') or ''
        
        query = text("""
            EXEC [dbo].[SP_Alta_Catalogo_Unidad_Academica]
                @UUnidad_Academica = :unidad_academica,
                @NNombre = :nombre,
                @CClave = :clave,
                @DDirector = :director,
                @IImagen = NULL,
                @RRama = :rama,
                @EEntidad = :entidad,
                @MMunicipio = :municipio,
                @CCalle = :calle,
                @NNumero = :numero,
                @CColonia = :colonia,
                @CCP = :cp,
                @UUsuario = :usuario,
                @HHost = :host,
                @PPeriodo = :periodo
        """)
        db.execute(query, {
            "unidad_academica": data.get("sigla"),
            "nombre": data.get("nombre"),
            "clave": data.get("clave"),
            "director": data.get("director"),
            "rama": data.get("rama"),
            "entidad": data.get("entidad"),
            "municipio": data.get("municipio"),
            "calle": data.get("calle"),
            "numero": int(data.get("numero")) if data.get("numero") else "SN",
            "colonia": data.get("colonia"),
            "cp": data.get("cp"),
            "usuario": UUsuario,
            "host": HHost, 
            "periodo": PPeriodo
        })
        db.commit()
        print("UA registrada correctamente")
    except Exception as e:
        db.rollback()
        print("Error al registrar UA:", e)
        return {"status": "error", "msg": "Error al registrar UA"}

    return {"status": "ok", "msg": "UA registrada correctamente"}


@router.put("/actualizarUA/")
def actualizar_ua(
    data: dict, 
    request: Request, 
    sess=Depends(get_current_session), 
    db: Session = Depends(get_db)
):
    id_rol = int(getattr(sess, 'id_rol', 0) or 0)
    if id_rol == 3:
        return {"status": "error", "msg": "No tienes permisos para realizar esta acción."}

    print("Body recibido en ACTUALIZAR:", data)
    try:
        # Obtener valores en tiempo de ejecución
        HHost = get_request_host(request)
        _, PPeriodo = get_periodo_activo(db) or get_ultimo_periodo(db)
        PPeriodo = PPeriodo or ""
        UUsuario = getattr(sess, 'usuario', '') or ''
        
        query = text("""
            EXEC [dbo].[SP_Modifica_Catalogo_Unidad_Academica]
                @UUnidad_Academica = :unidad_academica,
                @NNueva_Sigla = :nueva_sigla,
                @NNombre = :nombre,
                @CClave = :clave,
                @DDirector = :director,
                @IImagen = NULL,
                @RRama = :rama,
                @UUsuario = :usuario,
                @HHost = :host,
                @PPeriodo = :periodo
        """)
        db.execute(query, {
            "unidad_academica": data.get("sigla_anterior"),
            "nueva_sigla": data.get("sigla"),
            "nombre": data.get("nombre"),
            "clave": data.get("clave"),
            "director": data.get("director"),
            "rama": data.get("rama"),
            "usuario": UUsuario,
            "host": HHost,
            "periodo": PPeriodo
        })
        db.commit()
        print("UA actualizada correctamente")
    except Exception as e:
        db.rollback()
        print("Error al actualizar UA:", e)
        return {"status": "error", "msg": "Error al actualizar UA"}
    
    return {"status": "ok",  "msg": "UA actualizada correctamente"}


@router.delete("/eliminarUA/{sigla}")
def eliminar_ua(
    sigla: str, 
    request: Request, 
    sess=Depends(get_current_session), 
    db: Session = Depends(get_db)
):
    id_rol = int(getattr(sess, 'id_rol', 0) or 0)
    if id_rol == 3:
        return {"status": "error", "msg": "No tienes permisos para realizar esta acción."}

    print("Sigla a ELIMINAR:", sigla)
    try:
        # Obtener valores en tiempo de ejecución
        HHost = get_request_host(request)
        _, PPeriodo = get_periodo_activo(db) or get_ultimo_periodo(db)
        PPeriodo = PPeriodo or ""
        UUsuario = getattr(sess, 'usuario', '') or ''
        
        query = text("""
            EXEC [dbo].[SP_Baja_Catalogo_Unidad_Academica]
                @UUnidad_Academica = :unidad_academica,
                @UUsuario = :usuario,
                @HHost = :host,
                @PPeriodo = :periodo
        """)    
        db.execute(query, {
            "unidad_academica": sigla,
            "usuario": UUsuario,
            "host": HHost,
            "periodo": PPeriodo
        })
        db.commit()
        print("UA eliminada correctamente")
    except Exception as e:
        db.rollback()
        print("Error al eliminar UA:", e)
        return {"status": "error", "msg": str(e)}

    return {"status": "ok", "msg": "UA eliminada correctamente"}