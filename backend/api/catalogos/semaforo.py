from fastapi import APIRouter, Request, Depends, Body
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.database.connection import get_db
from backend.core.templates import templates
from backend.core.auth import get_current_session
from backend.services.periodo_service import get_ultimo_periodo, get_periodo_activo
from backend.utils.request import get_request_host  # Importamos la utilidad del host

router = APIRouter()


@router.get("/semaforo", response_class=HTMLResponse)
def semaforo_view(
    request: Request, 
    sess=Depends(get_current_session),
    db: Session = Depends(get_db)
):
    # 1. Obtener datos reales de sesión y host dinámico
    HHost = get_request_host(request)
    UUsuario = getattr(sess, 'nombre_usuario', '') or ''
    Rol = getattr(sess, 'nombre_rol', '') or ''
    id_rol = int(sess.id_rol)
    
    # 2. Validación directa del id_rol == 3
    if id_rol == 3:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_message": "No tienes permisos para acceder a este formato.",
            "redirect_url": "/mod_principal/",
            "session": sess
        })
    
    # Obtener periodo dinámico (priorizar activo)
    _, PPeriodo = get_periodo_activo(db) or get_ultimo_periodo(db)
    if not PPeriodo:
        PPeriodo = ""  # Valor vacío si no hay periodo

    try:
        # Ejecutar el Stored Procedure con parámetros nombrados
        query = text("""
            EXEC dbo.SP_Consulta_Catalogo_Semaforo
                @UUsuario = :UUsuario,
                @HHost = :HHost,
                @PPeriodo = :PPeriodo
        """)
        resultado = db.execute(query, {
            "UUsuario": UUsuario,
            "HHost": HHost,
            "PPeriodo": PPeriodo
        })

        # Convertir el resultado a lista de diccionarios
        data = [dict(row) for row in resultado.mappings().all()]
        print(data)

    except Exception as e:
        print("Error al ejecutar SP_Consulta_Catalogo_Semaforo:", e)
        data = []

    # Renderizar la plantilla HTML con los resultados
    return templates.TemplateResponse(
        "catalogos/semaforo.html",
        {
            "request": request,
            "semaforo": data,
            "rol": Rol,
            "session": sess
        }
    )


@router.post("/semaforo/registrar")
async def registrar_semaforo(
    data: dict, 
    request: Request, 
    sess=Depends(get_current_session)
):
    id_rol = int(sess.id_rol)
    if id_rol == 3:
        return JSONResponse(
            content={"status": "error", "mensaje": "No tienes permisos para realizar esta acción."},
            status_code=403
        )

    print("Registrando semáforo:", data)
    # Aquí puedes usar get_request_host(request) si necesitas mandarlo a un SP más adelante
    return JSONResponse(
        content={"mensaje": "Registrado correctamente"},
        status_code=200
    )


@router.put("/semaforo/actualizar")  # <-- Se corrigió el decorador añadiendo el '@'
async def actualizar_semaforo(
    data: dict, 
    request: Request, 
    sess=Depends(get_current_session)
):
    id_rol = int(sess.id_rol)
    if id_rol == 3:
        return JSONResponse(
            content={"status": "error", "mensaje": "No tienes permisos para realizar esta acción."},
            status_code=403
        )

    print("Actualizando semáforo:", data)
    return JSONResponse(
        content={"mensaje": "Actualizado correctamente"},
        status_code=200
    )