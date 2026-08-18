import os
import unicodedata
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from sqlalchemy.orm import Session 

from backend.core.templates import templates
from backend.core.auth import get_current_session
from backend.database.connection import get_db
from backend.services.usuario_service import is_super_admin
from backend.core.security_logger import (
    obtener_registros_seguridad,
    obtener_metricas_seguridad,
    obtener_ruta_csv,
)

router = APIRouter()


def _es_administrador_autorizado(sess) -> bool:
    """Verifica si la sesión corresponde a un Administrador (id_rol == 1) o SuperAdmin."""
    id_rol = int(getattr(sess, "id_rol", 0) or 0)
    nombre_usuario = getattr(sess, "nombre_usuario", "") or ""
    apellidoP_usuario = getattr(sess, "apellidoP_usuario", "") or ""
    apellidoM_usuario = getattr(sess, "apellidoM_usuario", "") or ""
    
    return id_rol == 1 or is_super_admin(nombre_usuario, apellidoP_usuario, apellidoM_usuario)


@router.get("/", response_class=HTMLResponse)
def mod_principal_view(request: Request, sess=Depends(get_current_session), db: Session = Depends(get_db)):
    nombre_usuario = sess.nombre_usuario
    apellidoP_usuario = sess.apellidoP_usuario
    apellidoM_usuario = sess.apellidoM_usuario
    nombre_completo = " ".join(filter(None, [nombre_usuario, apellidoP_usuario, apellidoM_usuario]))
    
    # 1. Obtener ID y Rol del usuario
    id_usuario = int(sess.id_usuario)
    id_rol = int(sess.id_rol)
    
    # 2. Definir qué roles son administradores (tienen acceso a todo sin revisar formato)
    es_admin = id_rol in [1, 4, 5, 6, 7, 8, 9] 
    es_super = _es_administrador_autorizado(sess)
    
    formatos_permitidos = []
    rechazos_por_modulo = {
        "matricula": None,
        "aprovechamiento": None,
        "egresados": None,
        "titulados": None
    }
    
    if not es_admin:
        # 3. Si es capturista, consultar sus formatos permitidos
        from backend.database.models.FormatoUsuario import Usuario as FormatoUsuario
        from backend.database.models.CatFormatos import CatFormatos
        # from backend.services.notificacion import notificacion_rechazo
        # from backend.services.periodo_service import get_periodo_activo, get_ultimo_periodo
        
        # periodo_id, _ = get_periodo_activo(db)
        # if not periodo_id:
        #     periodo_id, _ = get_ultimo_periodo(db)
            
        # id_ua = int(getattr(sess, "id_unidad_academica", 0) or 0)
        # id_nivel = int(getattr(sess, "id_nivel", 0) or 0)
        
        formatos = db.query(CatFormatos.Id_Formato, CatFormatos.Formato).join(
            FormatoUsuario, FormatoUsuario.Id_Formato == CatFormatos.Id_Formato
        ).filter(
            FormatoUsuario.Id_Usuario == id_usuario,
            FormatoUsuario.Id_Estatus == 1,
            CatFormatos.Id_Estatus == 1
        ).all()
        
        # 4. Normalizar los nombres (minúsculas y sin acentos)
        for id_fmt, f_nombre in formatos:
            nombre_fmt = f_nombre.lower().strip()
            nombre_fmt = ''.join(c for c in unicodedata.normalize('NFD', nombre_fmt) if unicodedata.category(c) != 'Mn')
            formatos_permitidos.append(nombre_fmt)
            
            # =========================================================================
            # NOTIFICACIÓN DE RECHAZO PARA CAPTURISTAS (id_rol == 3)
            # (Descomentar este bloque cuando se desee activar la detección de rechazo)
            # =========================================================================
            # if id_rol == 3 and periodo_id and id_ua:
            #     try:
            #         info_rechazo = notificacion_rechazo(db, periodo_id, id_ua, int(id_fmt), id_nivel if id_nivel > 0 else None)
            #         if info_rechazo:
            #             if id_fmt == 1:
            #                 rechazos_por_modulo["matricula"] = info_rechazo
            #             elif id_fmt == 2:
            #                 rechazos_por_modulo["aprovechamiento"] = info_rechazo
            #             elif id_fmt == 3:
            #                 rechazos_por_modulo["egresados"] = info_rechazo
            #             elif id_fmt == 4:
            #                 rechazos_por_modulo["titulados"] = info_rechazo
            #     except Exception as e:
            #         print(f"[ModPrincipal] Error al verificar rechazo formato {id_fmt}: {e}")

    return templates.TemplateResponse("Mod_Principal.html", {
        "request": request, 
        "nombre_usuario": nombre_completo, 
        "session": sess,
        "es_admin": es_admin,
        "es_super_admin": es_super,
        "formatos_permitidos": formatos_permitidos,
        "rechazos_por_modulo": rechazos_por_modulo
    })


@router.get("/dashboard_matricula", response_class=HTMLResponse)
def dashboard_matricula_view(request: Request, sess=Depends(get_current_session)):
    """Página del dashboard de Matrícula embebido de Power BI"""
    return templates.TemplateResponse("dashboard_matricula.html", {"request": request, "session": sess})


# ==============================================================================
# MÓDULO EXCLUSIVO DE AUDITORÍA Y SEGURIDAD (ADMINISTRADOR id_rol = 1)
# ==============================================================================

@router.get("/seguridad", response_class=HTMLResponse)
def auditoria_seguridad_view(
    request: Request,
    mes: Optional[str] = Query(default=None),
    sess=Depends(get_current_session)
):
    """
    Vista del Módulo de Auditoría de Seguridad.
    Permite consultar incidentes, bloqueos por Rate Limit, anomalías IDOR y descargar el archivo CSV.
    Restringido estrictamente a Administradores (id_rol = 1 / SuperAdmin).
    """
    if not _es_administrador_autorizado(sess):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: El módulo de auditoría de seguridad está reservado exclusivamente para el Administrador."
        )

    metricas = obtener_metricas_seguridad(mes)
    registros = obtener_registros_seguridad(mes_anio=mes, limite=500)
    
    from backend.core.rate_limiter import obtener_bloqueos_activos, desbloquear_identidad
    bloqueos_activos = obtener_bloqueos_activos()

    nombre_usuario = " ".join(filter(None, [sess.nombre_usuario, sess.apellidoP_usuario, sess.apellidoM_usuario]))

    return templates.TemplateResponse("auditoria_seguridad.html", {
        "request": request,
        "session": sess,
        "nombre_usuario": nombre_usuario,
        "metricas": metricas,
        "registros": registros,
        "bloqueos_activos": bloqueos_activos,
        "mes_seleccionado": mes or metricas["mes_actual"]
    })


@router.get("/seguridad/descargar-csv")
def descargar_csv_seguridad(
    mes: Optional[str] = Query(default=None),
    sess=Depends(get_current_session)
):
    """
    Descarga el archivo CSV de auditoría mensual de seguridad con codificación UTF-8 con BOM.
    """
    if not _es_administrador_autorizado(sess):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para descargar el reporte de auditoría."
        )

    ruta_csv = obtener_ruta_csv(mes)
    if not os.path.exists(ruta_csv):
        # Crear archivo vacío con cabeceras para que siempre se pueda descargar
        from backend.core.security_logger import _ensure_logs_dir, CSV_HEADERS
        import csv
        _ensure_logs_dir()
        with open(ruta_csv, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADERS)

    nombre_archivo = os.path.basename(ruta_csv)
    return FileResponse(
        path=ruta_csv,
        filename=nombre_archivo,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'}
    )


@router.get("/seguridad/datos", response_class=JSONResponse)
def datos_seguridad_ajax(
    mes: Optional[str] = Query(default=None),
    sess=Depends(get_current_session)
):
    """API JSON para actualizar datos y métricas en tiempo real."""
    if not _es_administrador_autorizado(sess):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")

    from backend.core.rate_limiter import obtener_bloqueos_activos
    metricas = obtener_metricas_seguridad(mes)
    registros = obtener_registros_seguridad(mes_anio=mes, limite=1000)
    bloqueos_activos = obtener_bloqueos_activos()
    return JSONResponse(content={
        "metricas": metricas,
        "registros": registros,
        "bloqueos_activos": bloqueos_activos
    })


@router.get("/seguridad/bloqueos-activos", response_class=JSONResponse)
def listar_bloqueos_activos_ajax(
    sess=Depends(get_current_session)
):
    """Retorna la lista de bloqueos en memoria que se encuentran activos en tiempo real."""
    if not _es_administrador_autorizado(sess):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")

    from backend.core.rate_limiter import obtener_bloqueos_activos
    bloqueos = obtener_bloqueos_activos()
    return JSONResponse(content={"bloqueos": bloqueos, "total": len(bloqueos)})


@router.post("/seguridad/desbloquear", response_class=JSONResponse)
async def desbloquear_usuario_manual(
    request: Request,
    sess=Depends(get_current_session)
):
    """
    Endpoint administrativo para desbloquear manualmente a un usuario o dispositivo.
    Elimina penalizaciones y registra el desbloqueo en la bitácora de auditoría CSV.
    """
    if not _es_administrador_autorizado(sess):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: Solo el Administrador puede realizar desbloqueos manuales."
        )

    # Extraer identificador desde JSON o Form
    identificador = ""
    try:
        data = await request.json()
        identificador = str(data.get("identificador", "")).strip()
    except Exception:
        form = await request.form()
        identificador = str(form.get("identificador", "")).strip()

    if not identificador:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe proporcionar el identificador, usuario o clave de rastreo a desbloquear."
        )

    from backend.core.rate_limiter import desbloquear_identidad
    admin_nombre = f"{sess.usuario} (ID:{sess.id_usuario})"
    eliminados = desbloquear_identidad(identificador=identificador, admin_usuario=admin_nombre)

    return JSONResponse(content={
        "success": True,
        "identificador": identificador,
        "bloqueos_eliminados": eliminados,
        "message": f"Identidad '{identificador}' desbloqueada exitosamente por {admin_nombre}."
    })
