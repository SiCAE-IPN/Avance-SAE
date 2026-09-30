# backend/core/auth.py
from __future__ import annotations

import os
from typing import Iterable, Optional

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.responses import Response
from fastapi import Query


from backend.core.session_store import SessionData, session_store
from backend.core.rate_limiter import detector_anomalias, get_client_ip

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

LEGACY_COOKIES = [
    "id_rol", "nombre_rol", "id_nivel", "nombre_nivel", "id_usuario", "usuario",
    "id_unidad_academica", "sigla_unidad_academica", "nombre_usuario", "apellidoP_usuario",
    "apellidoM_usuario", "requiere_cambio_password", "unidad_sigla", "username", "Usuario",
    "rol", "nivel", "unidad"
]

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
    # Limpiar cookies innecesarias del navegador para dejar solo session_id
    for legacy in LEGACY_COOKIES:
        try:
            response.delete_cookie(legacy, path="/")
        except Exception:
            pass

def clear_session_cookie(response: Response) -> None:
    response.delete_cookie("session_id", path="/")
    for legacy in LEGACY_COOKIES:
        try:
            response.delete_cookie(legacy, path="/")
        except Exception:
            pass

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

    # 1. Los administradores globales nunca son suspendidos en sus sesiones
    id_rol = int(getattr(sess, "id_rol", 0) or 0)
    nombre_rol = (getattr(sess, "nombre_rol", "") or "").strip().lower()
    es_admin = id_rol in [1, 6, 7, 8, 9] or nombre_rol in ["administrador", "analista", "jefe de departamento", "jefe de división", "directora"]

    # 2. Para otros roles, verificar si su cuenta o IP están temporalmente suspendidos por anomalías (E3)
    if not es_admin:
        client_ip = get_client_ip(request)
        ident_user = str(getattr(sess, "id_usuario", "") or getattr(sess, "usuario", "") or "")
        
        bloqueado_user, retry_user = detector_anomalias.esta_bloqueado(ident_user, penalizar_insistencia=False)
        bloqueado_ip = False
        retry_ip = 0
        if client_ip != "unknown" and client_ip not in ["127.0.0.1", "localhost", "::1"]:
            bloqueado_ip, retry_ip = detector_anomalias.esta_bloqueado(client_ip, penalizar_insistencia=False)

        if bloqueado_user or bloqueado_ip:
            retry_final = max(retry_user, retry_ip, 60)
            print(f"[seguridad] Acceso bloqueado por anomalías activas: Usuario={ident_user}, IP={client_ip}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Acceso temporalmente suspendido por detección de patrones anómalos. Por favor espere {retry_final} segundos.",
                headers={"Retry-After": str(retry_final)}
            )

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
        request: Request,
        ua_id: int, # FastAPI tomará este valor automáticamente de la URL
        sess: SessionData = Depends(get_current_session)
    ) -> SessionData:
        id_rol = int(getattr(sess, 'id_rol', 0) or 0)
        nombre_rol = (getattr(sess, 'nombre_rol', '') or '').strip().lower()

        # 1. Administradores globales en el sistema
        es_admin = id_rol in [1, 6, 7, 8, 9] or nombre_rol in ["administrador", "analista", "jefe de departamento", "jefe de división", "directora"]
        if es_admin:
            return sess

        # 2. Verificar si el usuario no admin se encuentra actualmente suspendido por comportamiento anómalo (E3)
        identificador = str(sess.id_usuario or sess.usuario or "desconocido")
        bloqueado, retry_after = detector_anomalias.esta_bloqueado(identificador)
        if bloqueado:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Acceso temporalmente suspendido por detección de anomalías. Por favor espere {retry_after} segundos.",
                headers={"Retry-After": str(retry_after)}
            )

        # 3. Si no es admin (ej. capturista, ceget, titular), verificamos su UA asignada
        ua_asignada = getattr(sess, 'id_unidad_academica', None)
        if ua_asignada is not None:
            ua_asignada = int(ua_asignada)

        if ua_asignada != int(ua_id):
            usuario_str = f"{sess.usuario} (ID:{sess.id_usuario})"
            print(f"[seguridad-IDOR] Intento de acceso no autorizado. Usuario {usuario_str} intentó acceder a UA {ua_id} (Asignada: {ua_asignada})")
            
            # Registrar incidente IDOR individual en la bitácora CSV de auditoría (E2)
            try:
                from backend.core.security_logger import registrar_bloqueo_seguridad
                registrar_bloqueo_seguridad(
                    request=request,
                    usuario_objetivo=usuario_str,
                    tipo_incidente="IDOR_ACCESO_NO_AUTORIZADO",
                    accion_tomada="ACCESO_DENEGADO_HTTP_403",
                    endpoint=f"/api/ua/{ua_id} (Asignada: UA {ua_asignada})"
                )
            except Exception as e:
                print(f"Error registrando IDOR en CSV: {e}")

            # Registrar en el detector de anomalías para barridos horizontales (E3)
            dev_id = getattr(request.state, "device_id", None) if hasattr(request, "state") else None
            detector_anomalias.registrar_intento_no_autorizado(
                user_id_or_ip=identificador,
                resource_id=f"UA_{ua_id}",
                endpoint=f"/api/ua/{ua_id}",
                device_id=dev_id
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado: No tienes permisos institucionales para consultar la Unidad Académica {ua_id}."
            )

        return sess

class VerificarAccesoInstitucional:
    """
    Dependencia para validar que el usuario no modifique la URL 
    para ver datos de otras Unidades Académicas o Niveles.
    """
    async def __call__(
        self,
        request: Request,
        ua_id: int, # Intercepta el {ua_id} de la URL
        nivel_id: int = None, # Intercepta el {nivel_id} de la URL de forma opcional
        sess: SessionData = Depends(get_current_session)
    ) -> SessionData:
        id_rol = int(getattr(sess, 'id_rol', 0) or 0)
        nombre_rol = (getattr(sess, 'nombre_rol', '') or '').strip().lower()

        # 1. Los administradores globales tienen acceso sin restricciones
        es_admin = id_rol in [1, 6, 7, 8, 9] or nombre_rol in ["administrador", "analista", "jefe de departamento", "jefe de división", "directora"]
        if es_admin:
            return sess

        # 2. Verificar si el usuario no admin se encuentra actualmente suspendido por comportamiento anómalo (E3)
        identificador = str(sess.id_usuario or sess.usuario or "desconocido")
        bloqueado, retry_after = detector_anomalias.esta_bloqueado(identificador)
        if bloqueado:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Acceso temporalmente suspendido por detección de anomalías. Por favor espere {retry_after} segundos.",
                headers={"Retry-After": str(retry_after)}
            )

        usuario_str = f"{sess.usuario} (ID:{sess.id_usuario})"

        # 3. Verificar la Unidad Académica
        ua_asignada = int(getattr(sess, 'id_unidad_academica', 0) or 0)
        if ua_asignada != int(ua_id):
            print(f"[seguridad-IDOR] Alerta: Usuario {usuario_str} intentó acceder a la UA {ua_id} (Asignada: {ua_asignada})")
            
            try:
                from backend.core.security_logger import registrar_bloqueo_seguridad
                registrar_bloqueo_seguridad(
                    request=request,
                    usuario_objetivo=usuario_str,
                    tipo_incidente="IDOR_ACCESO_NO_AUTORIZADO",
                    accion_tomada="ACCESO_DENEGADO_HTTP_403",
                    endpoint=f"/matricula/{ua_id} (Asignada: UA {ua_asignada})"
                )
            except Exception as e:
                print(f"Error registrando IDOR en CSV: {e}")

            dev_id = getattr(request.state, "device_id", None) if hasattr(request, "state") else None
            detector_anomalias.registrar_intento_no_autorizado(
                user_id_or_ip=identificador,
                resource_id=f"UA_{ua_id}",
                endpoint="/api/institucional",
                device_id=dev_id
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: No perteneces a esta Unidad Académica."
            )
            
        # 4. Verificar el Nivel (si la URL contiene un {nivel_id})
        # Roles como CEGET (4) y Titular (5) gestionan todos los niveles de su Unidad Académica
        es_ceget_o_titular = id_rol in [4, 5] or "ceget" in nombre_rol or "titular" in nombre_rol
        if not es_ceget_o_titular:
            nivel_asignado = int(getattr(sess, 'id_nivel', 0) or 0)
            if nivel_id is not None and nivel_asignado != int(nivel_id):
                print(f"[seguridad-IDOR] Alerta: Usuario {usuario_str} intentó acceder al nivel {nivel_id} (Asignado: {nivel_asignado})")
                
                try:
                    from backend.core.security_logger import registrar_bloqueo_seguridad
                    registrar_bloqueo_seguridad(
                        request=request,
                        usuario_objetivo=usuario_str,
                        tipo_incidente="IDOR_ACCESO_NO_AUTORIZADO",
                        accion_tomada="ACCESO_DENEGADO_HTTP_403",
                        endpoint=f"/matricula/{ua_id}/{nivel_id} (Asignado: Nivel {nivel_asignado})"
                    )
                except Exception as e:
                    print(f"Error registrando IDOR en CSV: {e}")

                dev_id = getattr(request.state, "device_id", None) if hasattr(request, "state") else None
                detector_anomalias.registrar_intento_no_autorizado(
                    user_id_or_ip=identificador,
                    resource_id=f"Nivel_{nivel_id}",
                    endpoint="/api/institucional",
                    device_id=dev_id
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Acceso denegado: No tienes permisos para este nivel académico."
                )

        return sess
    
async def verificar_acceso_acuse_dep(
    request: Request,
    sess: SessionData = Depends(get_current_session)
) -> SessionData:
    """
    Dependencia para validar los Query Params de la URL (?periodo=...&unidad=...&nivel=...)
    frente a los datos guardados en la sesión del usuario y las restricciones de periodo activo.
    """
    id_rol = int(getattr(sess, 'id_rol', 0) or 0)
    nombre_rol = (getattr(sess, 'nombre_rol', '') or '').strip().lower()

    # 1. Administradores globales (pueden ver cualquier UA, Nivel y Periodo histórico)
    es_admin = id_rol in [1, 6, 7, 8, 9] or nombre_rol in ["administrador", "analista", "jefe de departamento", "jefe de división", "directora"]
    if es_admin:
        return sess

    # 2. Verificar si el usuario no admin se encuentra actualmente suspendido por comportamiento anómalo (E3)
    identificador = str(sess.id_usuario or sess.usuario or "desconocido")
    bloqueado, retry_after = detector_anomalias.esta_bloqueado(identificador)
    if bloqueado:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Acceso temporalmente suspendido por detección de anomalías. Por favor espere {retry_after} segundos.",
            headers={"Retry-After": str(retry_after)}
        )

    # Extraer periodo, unidad y nivel de los Query Params de la petición
    raw_periodo = request.query_params.get("periodo") or request.query_params.get("periodo_id") or request.query_params.get("Id_Periodo")
    raw_unidad = request.query_params.get("unidad") or request.query_params.get("sigla")
    raw_unidad_id = request.query_params.get("id_unidad") or request.query_params.get("unidad_id") or request.query_params.get("Id_Unidad_Academica")
    raw_nivel = request.query_params.get("nivel") or request.query_params.get("id_nivel") or request.query_params.get("Id_Nivel")

    usuario_str = f"{sess.usuario} (ID:{sess.id_usuario})"
    search_periodo = (raw_periodo or "").strip()
    search_unidad = (raw_unidad or "").strip()
    search_nivel = (raw_nivel or "").strip()

    # 3. Validar Periodo Escolar (Roles 3, 4 y 5 solo pueden consultar periodos activos/autorizados)
    if search_periodo:
        try:
            from backend.database.connection import SessionLocal
            from backend.services.periodo_service import get_periodo_activo, get_periodo_anterior_al_ultimo
            db_auth = SessionLocal()
            try:
                p_act_tuple = get_periodo_activo(db_auth)
                p_ant_tuple = get_periodo_anterior_al_ultimo(db_auth)
                
                periodos_permitidos = []
                if p_act_tuple:
                    if p_act_tuple[0] is not None:
                        periodos_permitidos.append(str(p_act_tuple[0]).strip().lower())
                    if p_act_tuple[1]:
                        periodos_permitidos.append(str(p_act_tuple[1]).strip().lower())
                if p_ant_tuple:
                    if p_ant_tuple[0] is not None:
                        periodos_permitidos.append(str(p_ant_tuple[0]).strip().lower())
                    if p_ant_tuple[1]:
                        periodos_permitidos.append(str(p_ant_tuple[1]).strip().lower())
            finally:
                db_auth.close()
        except Exception as e:
            print(f"[auth-periodo] Error obteniendo periodos activos: {e}")
            periodos_permitidos = []

        if periodos_permitidos and search_periodo.lower() not in periodos_permitidos:
            print(f"[seguridad-IDOR] Bloqueado: {usuario_str} intentó cambiar URL al periodo: {search_periodo} (Permitidos: {periodos_permitidos})")
            
            try:
                from backend.core.security_logger import registrar_bloqueo_seguridad
                registrar_bloqueo_seguridad(
                    request=request,
                    usuario_objetivo=usuario_str,
                    tipo_incidente="IDOR_ACCESO_NO_AUTORIZADO",
                    accion_tomada="ACCESO_DENEGADO_HTTP_403",
                    endpoint=f"{request.url.path}?periodo={search_periodo}"
                )
            except Exception as e:
                print(f"Error registrando IDOR en CSV: {e}")

            dev_id = getattr(request.state, "device_id", None) if hasattr(request, "state") else None
            detector_anomalias.registrar_intento_no_autorizado(
                user_id_or_ip=identificador,
                resource_id=f"Periodo_{search_periodo}",
                endpoint=request.url.path,
                device_id=dev_id
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: No tienes permisos para consultar otros periodos escolares."
            )

    # 4. Validar la Unidad Académica contra sus siglas/ID en la sesión
    sigla_sess = (getattr(sess, 'sigla_unidad_academica', '') or "").strip().lower()
    id_ua_sess = int(getattr(sess, 'id_unidad_academica', 0) or 0)

    # Normalizar eliminando espacios para tolerar "CMP L" == "CMPL" por efectos de URL encoding
    sigla_sess_norm = sigla_sess.replace(" ", "")
    search_unidad_norm = search_unidad.lower().replace(" ", "")
    if search_unidad and sigla_sess and sigla_sess_norm != search_unidad_norm:
        print(f"[seguridad-IDOR] Bloqueado: {usuario_str} intentó cambiar URL a la unidad: {search_unidad} (Asignada: {sigla_sess})")
        
        try:
            from backend.core.security_logger import registrar_bloqueo_seguridad
            registrar_bloqueo_seguridad(
                request=request,
                usuario_objetivo=usuario_str,
                tipo_incidente="IDOR_ACCESO_NO_AUTORIZADO",
                accion_tomada="ACCESO_DENEGADO_HTTP_403",
                endpoint=f"{request.url.path}?unidad={search_unidad} (Asignada: {sigla_sess})"
            )
        except Exception as e:
            print(f"Error registrando IDOR en CSV: {e}")

        dev_id = getattr(request.state, "device_id", None) if hasattr(request, "state") else None
        detector_anomalias.registrar_intento_no_autorizado(
            user_id_or_ip=identificador,
            resource_id=f"UA_{search_unidad}",
            endpoint=request.url.path,
            device_id=dev_id
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: No tienes permisos para consultar esta Unidad Académica."
        )

    if raw_unidad_id and id_ua_sess > 0:
        try:
            if int(raw_unidad_id) != id_ua_sess:
                raise ValueError("UA ID mismatch")
        except (ValueError, TypeError):
            print(f"[seguridad-IDOR] Bloqueado: {usuario_str} intentó cambiar URL al ID de unidad: {raw_unidad_id} (Asignada ID: {id_ua_sess})")
            try:
                from backend.core.security_logger import registrar_bloqueo_seguridad
                registrar_bloqueo_seguridad(
                    request=request,
                    usuario_objetivo=usuario_str,
                    tipo_incidente="IDOR_ACCESO_NO_AUTORIZADO",
                    accion_tomada="ACCESO_DENEGADO_HTTP_403",
                    endpoint=f"{request.url.path}?id_unidad={raw_unidad_id} (Asignada ID: {id_ua_sess})"
                )
            except Exception as e:
                print(f"Error registrando IDOR en CSV: {e}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: No tienes permisos para consultar esta Unidad Académica."
            )

    # 5. Validar el Nivel Académico solo si el rol está restringido por nivel (ej. Capturista = 3).
    # Roles como CEGET (4) y Titular (5) gestionan todos los niveles de su Unidad Académica.
    es_ceget_o_titular = id_rol in [4, 5] or "ceget" in nombre_rol or "titular" in nombre_rol
    if not es_ceget_o_titular:
        nivel_sess = (getattr(sess, 'nombre_nivel', '') or "").strip().lower()
        if search_nivel and nivel_sess and nivel_sess != search_nivel.lower():
            print(f"[seguridad-IDOR] Bloqueado: {usuario_str} intentó cambiar URL al nivel: {search_nivel} (Asignado: {nivel_sess})")
            
            try:
                from backend.core.security_logger import registrar_bloqueo_seguridad
                registrar_bloqueo_seguridad(
                    request=request,
                    usuario_objetivo=usuario_str,
                    tipo_incidente="IDOR_ACCESO_NO_AUTORIZADO",
                    accion_tomada="ACCESO_DENEGADO_HTTP_403",
                    endpoint=f"{request.url.path}?nivel={search_nivel} (Asignado: {nivel_sess})"
                )
            except Exception as e:
                print(f"Error registrando IDOR en CSV: {e}")

            dev_id = getattr(request.state, "device_id", None) if hasattr(request, "state") else None
            detector_anomalias.registrar_intento_no_autorizado(
                user_id_or_ip=identificador,
                resource_id=f"Nivel_{search_nivel}",
                endpoint=request.url.path,
                device_id=dev_id
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: No tienes permisos para consultar este nivel académico."
            )
    
    return sess


def VerificarAccesoAcuse():
    """Función constructora para compatibilidad con `validar_acuse = VerificarAccesoAcuse()`."""
    return verificar_acceso_acuse_dep
