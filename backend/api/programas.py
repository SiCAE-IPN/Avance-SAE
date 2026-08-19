from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from backend.core.templates import templates
from backend.core.auth import get_current_session
from backend.database.connection import get_db
from sqlalchemy.orm import Session
from sqlalchemy import join
from backend.database.models.CatProgramas import CatProgramas
from backend.database.models.ProgramaModalidad import ProgramaModalidad
from backend.database.models.UnidadProgramaModalidad import CatUnidadProgramaModalidad
from backend.database.models.CatUnidadAcademica import CatUnidadAcademica
from backend.database.models.CatModalidad import CatModalidad
from backend.services.periodo_service import get_periodo_activo, get_ultimo_periodo
from backend.database.models.CatNivel import CatNivel

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def programas_view(request: Request, sess=Depends(get_current_session), db: Session = Depends(get_db)):
    # Obtener datos del usuario logueado desde las cookies
    id_unidad_academica = int(sess.id_unidad_academica)
    id_rol = int(sess.id_rol)
    nombre_usuario = sess.nombre_usuario
    apellidoP_usuario = sess.apellidoP_usuario
    apellidoM_usuario = sess.apellidoM_usuario
    
    # Verificar si es super admin
    es_super_admin = (nombre_usuario.strip().lower() == 'admin' and
                     apellidoP_usuario.strip().lower() == 'admin' and
                     apellidoM_usuario.strip().lower() == 'admin')
    
    _, periodo_literal = get_periodo_activo(db) or get_ultimo_periodo(db)
    periodo_literal = periodo_literal or ""

    # Si es super admin, obtener todas las UAs para el selector
    todas_uas = []
    if es_super_admin:
        todas_uas = db.query(CatUnidadAcademica).order_by(CatUnidadAcademica.Nombre).all()
        
    # Obtener programas según el rol
    if es_super_admin:
        # Para super admin, inicialmente mostrar los de la primera UA o vacío
        unidad_academica = db.query(CatUnidadAcademica).first()
        if unidad_academica:
            id_unidad_academica = unidad_academica.Id_Unidad_Academica
        else:
            id_unidad_academica = 0
            
    # Obtener los programas de la unidad académica del usuario
    programas_unidad = db.query(CatUnidadProgramaModalidad).filter_by(Id_Unidad_Academica=id_unidad_academica).all()
    
    # Agrupar por unidad académica
    programas_por_ua = {}
    if id_unidad_academica > 0:
        unidad_academica = db.query(CatUnidadAcademica).filter_by(Id_Unidad_Academica=id_unidad_academica).first()
        
        programas_info = []
        for pup in programas_unidad:
            pm = db.query(ProgramaModalidad).filter_by(Id_Modalidad_Programa=pup.Id_Modalidad_Programa).first()
            if not pm:
                continue
                
            programa = db.query(CatProgramas).filter_by(Id_Programa=pm.Id_Programa).first()
            if not programa:
                continue
                
            modalidad = db.query(CatModalidad).filter_by(Id_Modalidad=pm.Id_Modalidad).first()
            nivel = db.query(CatNivel).filter_by(Id_Nivel=programa.Id_Nivel).first()
            
            programas_info.append({
                'nombre_programa': programa.Nombre_Programa,
                'modalidad': modalidad.Modalidad if modalidad else 'Sin modalidad',
                'nivel': nivel.Nivel if nivel else 'Sin nivel'
            })
        
        if unidad_academica and programas_info:
            ua_key = f"{unidad_academica.Sigla} - {unidad_academica.Nombre}"
            programas_por_ua[ua_key] = programas_info

    return templates.TemplateResponse(
        "programas.html",
        {
            "request": request,
            "programas_por_ua": programas_por_ua,
            "es_super_admin": es_super_admin,
            "todas_uas": todas_uas,
            "nombre_usuario": sess.nombre_completo,
            "nombre_rol": sess.nombre_rol,
            "sigla_unidad_academica": sess.sigla_unidad_academica,
            "periodo_literal": periodo_literal,
            "session": sess,
        }
    )


# Endpoint para obtener programas de una UA específica (solo superadmin)
@router.get("/por-ua/{id_ua}", response_class=JSONResponse)
async def programas_por_ua(id_ua: int, request: Request, sess=Depends(get_current_session), db: Session = Depends(get_db)):
    nombre_usuario = sess.nombre_usuario
    apellidoP_usuario = sess.apellidoP_usuario
    apellidoM_usuario = sess.apellidoM_usuario
    es_super_admin = (nombre_usuario.strip().lower() == 'admin' and
                     apellidoP_usuario.strip().lower() == 'admin' and
                     apellidoM_usuario.strip().lower() == 'admin')
    if not es_super_admin:
        return JSONResponse(status_code=403, content={"error": "No autorizado"})

    unidad_academica = db.query(CatUnidadAcademica).filter_by(Id_Unidad_Academica=id_ua).first()
    if not unidad_academica:
        return JSONResponse(status_code=404, content={"error": "Unidad Académica no encontrada"})

    upms = db.query(CatUnidadProgramaModalidad).filter_by(Id_Unidad_Academica=id_ua).all()
    programas_info = []
    for upm in upms:
        pm = db.query(ProgramaModalidad).filter_by(Id_Modalidad_Programa=upm.Id_Modalidad_Programa).first()
        if not pm:
            continue
        programa = db.query(CatProgramas).filter_by(Id_Programa=pm.Id_Programa).first()
        if not programa:
            continue
        modalidad = db.query(CatModalidad).filter_by(Id_Modalidad=pm.Id_Modalidad).first()
        nivel = db.query(CatNivel).filter_by(Id_Nivel=programa.Id_Nivel).first()
        programas_info.append({
            'nombre_programa': programa.Nombre_Programa,
            'modalidad': modalidad.Modalidad if modalidad else 'Sin modalidad',
            'nivel': nivel.Nivel if nivel else 'Sin nivel'
        })
    return {"programas": programas_info, "ua": f"{unidad_academica.Sigla} - {unidad_academica.Nombre}"}
