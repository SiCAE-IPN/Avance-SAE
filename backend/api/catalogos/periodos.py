from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.database.connection import get_db
from backend.core.templates import templates
from backend.core.auth import get_current_session
from backend.services.periodo_service import get_ultimo_periodo, get_periodo_activo
from backend.utils.request import get_request_host  # Importamos la utilidad del host
from backend.database.models.CatPeriodo import CatPeriodo

router = APIRouter()


@router.get("/periodos", response_class=HTMLResponse)
def periodos_view(
    request: Request, 
    sess=Depends(get_current_session),
    db: Session = Depends(get_db)
):
    # 1. Obtener el Host dinámicamente desde la petición
    HHost = get_request_host(request)
    
    UUsuario = str(sess.nombre_usuario)
    Rol = str(sess.nombre_rol)
    id_rol = int(sess.id_rol)  # Obtenemos el id_rol de la sesión
    
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
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_message": "No hay periodos configurados en el sistema.",
            "redirect_url": "/mod_principal/",
            "session": sess
        })
    
    try:
        # Ejecutar el Stored Procedure con parámetros nombrados
        query = text("""
            EXEC dbo.SP_Consulta_Catalogo_Periodos
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

        # Enriquecer cada fila con las fechas del periodo (el SP no las incluye)
        periodos_orm = {p.Periodo: p for p in db.query(CatPeriodo).all()}
        for fila in data:
            periodo_orm = periodos_orm.get(fila.get("Periodo"))
            fila["Fecha_Inicio_Periodo"] = periodo_orm.Fecha_Inicio_Periodo if periodo_orm else None
            fila["Fecha_Final_Periodo"] = periodo_orm.Fecha_Final_Periodo if periodo_orm else None

        print(data)

    except Exception as e:
        print("Error al ejecutar SP_Consulta_Catalogo_Periodos:", e)
        data = []

    # Renderizar la plantilla HTML con los resultados
    return templates.TemplateResponse(
        "catalogos/periodos.html",
        {
            "request": request,
            "periodos": data,
            "rol": Rol,
            "nombre_rol": Rol,
            "nombre_usuario": getattr(sess, 'nombre_completo', '') or getattr(sess, 'nombre_usuario', ''),
            "sigla_unidad_academica": getattr(sess, 'sigla_unidad_academica', ''),
            "periodo_literal": PPeriodo,
            "session": sess
        }
    )


@router.post("/nuevo_periodo")  
def nuevo_periodo(
    request: Request, 
    data: dict, 
    sess=Depends(get_current_session), 
    db: Session = Depends(get_db)
):
    # Obtener el Host dinámicamente para la bitácora del SP
    HHost = get_request_host(request)
    UUsuario = str(sess.usuario)
    id_rol = int(sess.id_rol)

    # También validamos el rol aquí por seguridad si intentan hacer POST directamente
    if id_rol == 3:
        return {"status": "error", "message": "No tienes permisos para realizar esta acción."}
    
    print(f"Creando periodo: {data['periodo']} por usuario: {UUsuario}")
    print(f"Fecha inicial: {data.get('fecha_inicial')}, Fecha final: {data.get('fecha_final')}")
    
    try:
        # PASO 1: Ejecutar el SP para crear el nuevo periodo
        print("📝 Creando nuevo periodo...")
        print(f"Parámetros para SP_Inicia_periodo:")
        print(f"  @PPeriodo = {data['periodo']}")
        print(f"  @FFecha_Inicial = {data['fecha_inicial']}")
        print(f"  @FFecha_Final = {data['fecha_final']}")
        print(f"  @HHost = {HHost}")
        print(f"  @UUsuario = {UUsuario}")

        query = text("""
            EXEC dbo.SP_Inicia_periodo
                @PPeriodo = :PPeriodo,
                @FFecha_Inicial = :FFecha_Inicial,
                @FFecha_Final = :FFecha_Final,
                @HHost = :HHost,
                @UUsuario = :UUsuario
        """)
        
        db.execute(query, {
            "PPeriodo": data["periodo"],
            "FFecha_Inicial": data["fecha_inicial"],
            "FFecha_Final": data["fecha_final"],
            "HHost": HHost,
            "UUsuario": UUsuario
        })
        
        db.commit()
        print("✅ Periodo creado exitosamente.")
        return {"status": "success", "message": "Periodo creado exitosamente."}
    except Exception as e:
        db.rollback()  # Añadido rollback en caso de fallo en la base de datos
        print("Error al crear nuevo periodo:", e)
        return {"status": "error", "message": "Error al crear nuevo periodo."}