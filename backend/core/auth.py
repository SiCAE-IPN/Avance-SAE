# backend/core/auth.py
from __future__ import annotations

import os
from typing import Iterable, Optional

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.responses import Response

from backend.core.session_store import SessionData, session_store

# Default: 8 hours
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", str(60 * 60 * 8)))

def is_secure_cookie() -> bool:
    """Secure cookies require HTTPS. In local dev you may run HTTP."""
    v = os.getenv("COOKIE_SECURE", "").strip().lower()
    if v in {"1", "true", "yes", "on"}:
        return True
    if v in {"0", "false", "no", "off"}:
        return False
    # Auto: secure in common hosted envs
    return os.getenv("ENV", "").lower() in {"prod", "production"} or os.getenv("HTTPS", "").lower() in {"on", "1", "true"}

def set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=is_secure_cookie(),
        samesite=os.getenv("COOKIE_SAMESITE", "lax"),
        max_age=SESSION_TTL_SECONDS,
        path="/",
    )

def clear_session_cookie(response: Response) -> None:
    response.delete_cookie("session_id", path="/")

async def get_current_session(
    request: Request,
    session_id: Optional[str] = Cookie(default=None),
) -> SessionData:
    # Debug: registrar si llega cookie
    try:
        print(f"[auth] Incoming request path={request.url.path} cookies={dict(request.cookies)}")
    except Exception:
        pass

    if not session_id:
        print("[auth] No session_id cookie present -> 401")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    sess = session_store.get(session_id)
    if not sess:
        print(f"[auth] session_id={session_id} not found or expired in session_store -> 401")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    else:
        try:
            print(f"[auth] session found: session_id={session_id} id_usuario={getattr(sess,'id_usuario',None)} id_rol={getattr(sess,'id_rol',None)} is_impersonating={getattr(sess,'is_impersonating',False)}")
        except Exception:
            pass
    # Sliding TTL (optional). Comment out if you prefer fixed expiry.
    session_store.touch(session_id, SESSION_TTL_SECONDS)
    request.state.session = sess
    request.state.session_id = session_id
    return sess

def require_roles(*allowed_roles: int):
    allowed = set(allowed_roles)
    async def _dep(sess: SessionData = Depends(get_current_session)) -> SessionData:
        if sess.id_rol not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return sess
    return _dep

class VerificarAccesoUA:
    """
    Dependencia para evitar ataques IDOR.
    Verifica que el usuario actual tenga permiso para acceder a la UA solicitada en la URL.
    """
    async def __call__(
        self,
        ua_id: int, # FastAPI tomará este valor automáticamente de la URL
        sess: SessionData = Depends(get_current_session)
    ) -> SessionData:
        
        # 1. Reutilizamos tu lógica: estos roles son administradores globales en el sistema
        es_admin = sess.id_rol in [1, 6, 7, 8, 9]

        if es_admin:
            return sess # Los administradores pueden ver cualquier URL

        # 2. Si no es admin (ej. capturista), verificamos su UA asignada
        # Nota: Asegúrate de que cuando creas la sesión (SessionData), estés guardando el 'id_ua' del usuario.
        ua_asignada = getattr(sess, 'id_', None)

        if ua_asignada != ua_id:
            print(f"[seguridad] Intento de acceso no autorizado. Usuario {sess.id_usuario} intentó acceder a UA {ua_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: No tienes permisos institucionales para consultar esta Unidad Académica."
            )

        return sess

class VerificarAccesoInstitucional:
    """
    Dependencia para validar que el usuario no modifique la URL 
    para ver datos de otras Unidades Académicas o Niveles.
    """
    async def __call__(
        self,
        ua_id: int, # Intercepta el {ua_id} de la URL
        nivel_id: int = None, # Intercepta el {nivel_id} de la URL de forma opcional
        sess: SessionData = Depends(get_current_session)
    ) -> SessionData:
        
        # 1. Los administradores globales tienen acceso sin restricciones
        es_admin = sess.id_rol in [1, 6, 7, 8, 9]
        if es_admin:
            return sess 

        # 2. Verificar la Unidad Académica
        if sess.id_unidad_academica != ua_id:
            print(f"[seguridad] Alerta: Usuario {sess.usuario} intentó acceder a la UA {ua_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: No perteneces a esta Unidad Académica."
            )
            
        # 3. Verificar el Nivel (si la URL contiene un {nivel_id})
        if nivel_id is not None and sess.id_nivel != nivel_id:
            print(f"[seguridad] Alerta: Usuario {sess.usuario} intentó acceder al nivel {nivel_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: No tienes permisos para este nivel académico."
            )

        return sess
    
from fastapi import Query

class VerificarAccesoAcuse:
    """
    Dependencia para validar los Query Params de la URL del acuse (?unidad=...&nivel=...)
    frente a los datos guardados en la sesión del usuario.
    """
    async def __call__(
        self,
        unidad: str = Query(...), # Captura de forma obligatoria el parámetro 'unidad'
        nivel: str = Query(...),  # Captura de forma obligatoria el parámetro 'nivel'
        sess: SessionData = Depends(get_current_session)
    ) -> SessionData:
        
        # 1. Tu lista de roles administradores (tienen permitido modificar la URL y ver todo)
        es_admin = sess.id_rol in [1, 6, 7, 8, 9]
        if es_admin:
            return sess

        # 2. Si no es admin, validar la Unidad Académica contra sus siglas en la sesión
        if sess.sigla_unidad_academica.strip().lower() != unidad.strip().lower():
            print(f"[seguridad] Bloqueado: {sess.usuario} intentó cambiar URL a la unidad: {unidad}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: No tienes permisos para consultar esta Unidad Académica."
            )

        # 3. Validar el Nivel Académico contra el nombre del nivel en la sesión
        if sess.nombre_nivel.strip().lower() != nivel.strip().lower():
            print(f"[seguridad] Bloqueado: {sess.usuario} intentó cambiar URL al nivel: {nivel}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: No tienes permisos para consultar este nivel académico."
            )

        return sess
