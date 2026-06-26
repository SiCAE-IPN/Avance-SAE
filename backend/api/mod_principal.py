from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from backend.core.templates import templates
from backend.core.auth import get_current_session
from backend.database.connection import get_db
from sqlalchemy.orm import Session 
import unicodedata

router = APIRouter()

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
    
    formatos_permitidos = []
    
    if not es_admin:
        # 3. Si es capturista, consultar sus formatos permitidos
        # Suponiendo que tu modelo Formato_Usuario se importó como "Usuario" o "FormatoUsuario"
        from backend.database.models.FormatoUsuario import Usuario as FormatoUsuario
        from backend.database.models.CatFormatos import CatFormatos
        
        formatos = db.query(CatFormatos.Formato).join(
            FormatoUsuario, FormatoUsuario.Id_Formato == CatFormatos.Id_Formato
        ).filter(
            FormatoUsuario.Id_Usuario == id_usuario,
            FormatoUsuario.Id_Estatus == 1,
            CatFormatos.Id_Estatus == 1
        ).all()
        
        # 4. Normalizar los nombres (minúsculas y sin acentos) para evitar errores de validación en HTML
        for f in formatos:
            nombre_fmt = f[0].lower().strip()
            nombre_fmt = ''.join(c for c in unicodedata.normalize('NFD', nombre_fmt) if unicodedata.category(c) != 'Mn')
            formatos_permitidos.append(nombre_fmt)

    return templates.TemplateResponse("Mod_Principal.html", {
        "request": request, 
        "nombre_usuario": nombre_completo, 
        "session": sess,
        "es_admin": es_admin,
        "formatos_permitidos": formatos_permitidos
    })

@router.get("/dashboard_matricula", response_class=HTMLResponse)
def dashboard_matricula_view(request: Request, sess=Depends(get_current_session)):
    """Página del dashboard de Matrícula embebido de Power BI"""
    return templates.TemplateResponse("dashboard_matricula.html", {"request": request, "session": sess})

