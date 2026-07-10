# backend/services/usuario_service.py
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Dict
from backend.database.models.FormatoUsuario import Usuario as FormatoUsuario
from backend.database.models.Usuario import Usuario
from fastapi import HTTPException, status



def obtener_encargados(db: Session, Id_Unidad_Academica: int, Id_formato: int) -> Dict[str, str]:
    """
    Busca los nombres del Capturista (filtrado por el formato asignado en Formato_Usuario),
    así como del CEGET y del Titular encargados de la Unidad Académica.
    
    Args:
        db (Session): Sesión de la base de datos.
        Id_Unidad_Academica (int): ID de la Unidad Académica.
        Id_formato (int): ID del formato (1 = Matrícula, 2 = Aprovechamiento, etc.)
        
    Returns:
        Dict[str, str]: Diccionario con los nombres completos de los involucrados.
    """

    encargados = {
        "nombre_capturista": "No asignado",
        "nombre_ceget": "No asignado",
        "nombre_titular": "No asignado"
    }

    try:
        # Construimos el query usando el ORM con un LEFT OUTER JOIN hacia FormatoUsuario
        usuarios = (
            db.query(
                Usuario.Nombre, 
                Usuario.Paterno, 
                Usuario.Materno, 
                Usuario.Id_Rol
            )
            .outerjoin(FormatoUsuario, Usuario.Id_Usuario == FormatoUsuario.Id_Usuario)
            .filter(
                Usuario.Id_Unidad_Academica == Id_Unidad_Academica,
                Usuario.Id_Estatus == 1,
                or_(
                    # Condición 1: Es capturista (Rol 3) y tiene asignado el formato solicitado
                    (Usuario.Id_Rol == 3) & (FormatoUsuario.Id_Formato == Id_formato),
                    # Condición 2: Es CEGET (Rol 4) o Titular (Rol 5) de la Unidad Académica
                    Usuario.Id_Rol.in_([4, 5])
                )
            )
            .all()
        )

        # Procesamos los resultados para armar los nombres completos
        for u in usuarios:
            # Filtramos componentes vacíos o None antes de unir con espacios
            partes_nombre = [str(p).strip() for p in [u.Nombre, u.Paterno, u.Materno] if p]
            nombre_completo = " ".join(partes_nombre).strip()

            if not nombre_completo:
                continue

            # Asignamos la variable correspondiente según el Id_Rol
            if u.Id_Rol == 3:
                encargados["nombre_capturista"] = nombre_completo
            elif u.Id_Rol == 4:
                encargados["nombre_ceget"] = nombre_completo
            elif u.Id_Rol == 5:
                encargados["nombre_titular"] = nombre_completo

        print(f"📋 [DEBUG ENCARGADOS] UA: {Id_Unidad_Academica} | Formato: {Id_formato} -> {encargados}")

    except Exception as e:
        print(f"❌ [ERROR ENCARGADOS] Error al obtener encargados por ORM: {str(e)}")

    return encargados

def verificar_permiso_formato(db: Session, usuario_id: int, formato_id: int):
    """
    Verifica si un usuario tiene registro en la tabla formatousuario.
    Si no existe, lanza una excepción HTTP 403 de FastAPI inmediatamente.
    """
    permiso_existe = db.query(FormatoUsuario).filter(
        FormatoUsuario.Id_Formato == usuario_id,
        FormatoUsuario.Id_Usuario == formato_id
    ).first()

    if not permiso_existe:
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: No tienes permisos institucionales para consultar este Formato."
        )
    
    return permiso_existe