# routers/login.py
import re
from backend.database.connection import get_db
from backend.services.usuario_service import validacion_usuario
from backend.schemas.Usuario import UsuarioLogin, UsuarioResponse
from backend.core.templates import templates, static
from backend.core.session_store import SessionData, session_store
from backend.core.auth import set_session_cookie, clear_session_cookie, SESSION_TTL_SECONDS, get_current_session

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from sqlalchemy.orm import Session

from typing import Optional

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def login_view(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/logout")
async def logout(request: Request):
    """Cierra sesión (borra sesión server-side y la cookie session_id)."""
    sid = request.cookies.get("session_id")
    if sid:
        session_store.delete(sid)
    resp = RedirectResponse(url="/login", status_code=303)
    clear_session_cookie(resp)
    return resp

from backend.core.rate_limiter import limiter_login

@router.post("/", response_class=HTMLResponse)
async def login(
    request: Request,
    usuario_email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
    _rate_limit = Depends(limiter_login)
):
    exito = False
    mensaje = ""
    try:
        if validacion_usuario(db, usuario_email, password):
            exito = True
            from backend.crud.Usuario import read_user_by_email, read_user_by_username
            from backend.database.models.CatRoles import CatRoles
            from backend.database.models.CatNivel import CatNivel
            from backend.database.models.CatUnidadAcademica import CatUnidadAcademica
            
            user = read_user_by_email(db, usuario_email)
            if user is None:
                user = read_user_by_username(db, usuario_email)

            id_unidad = user.Id_Unidad_Academica if user else 1
            id_rol = user.Id_Rol if user else 2
            id_nivel = user.Id_Nivel if user else 1
            id_usuario = user.Id_Usuario if user else None
            
            # Obtener nombres del rol, nivel y sigla de la unidad académica
            rol = db.query(CatRoles).filter(CatRoles.Id_Rol == id_rol).first()
            nivel = db.query(CatNivel).filter(CatNivel.Id_Nivel == id_nivel).first()
            unidad = db.query(CatUnidadAcademica).filter(CatUnidadAcademica.Id_Unidad_Academica == id_unidad).first()
            
            nombre_rol = rol.Rol if rol else "Usuario"
            nombre_nivel = nivel.Nivel if nivel else "No definido"
            sigla_unidad = unidad.Sigla if unidad else ""
            nombre_unidad = unidad.Nombre if unidad else ""
            
            print(f"DEBUG LOGIN: Usuario {user.Usuario}")
            print(f"DEBUG LOGIN: ID Rol: {id_rol}, Nombre Rol: {nombre_rol}")
            print(f"DEBUG LOGIN: ID Nivel: {id_nivel}, Nombre Nivel: {nombre_nivel}")
            print(f"DEBUG LOGIN: ID Unidad Académica: {id_unidad}")
            
            # Verificar si tiene contraseña temporal usando bitácora
            from backend.services.usuario_service import has_temporary_password
            temp_password_detected = has_temporary_password(db, user.Id_Usuario)
            print(f"DEBUG: Usuario {user.Usuario} - Contraseña temporal detectada: {temp_password_detected}")
            
            if temp_password_detected:
                # Si tiene contraseña temporal, redirigir a cambiar_password
                response = RedirectResponse(url="/recuperacion/cambiar", status_code=303)
                print(f"DEBUG: Redirigiendo a /recuperacion/cambiar")
            else:
                # Redirigir a la vista principal después de login
                response = RedirectResponse(url="/mod_principal", status_code=303)
                print(f"DEBUG: Redirigiendo a /mod_principal")

            # Crear sesión server-side (no confiar en cookies editables)
            sess = SessionData(
                id_usuario=int(id_usuario or 0),
                usuario=user.Usuario or "",
                id_rol=int(id_rol or 0),
                nombre_rol=nombre_rol or "",
                id_nivel=int(id_nivel or 0),
                nombre_nivel=nombre_nivel or "",
                id_unidad_academica=int(id_unidad or 0),
                sigla_unidad_academica=sigla_unidad or "",
                nombre_usuario=user.Nombre or "",
                apellidoP_usuario=user.Paterno or "",
                apellidoM_usuario=user.Materno or "",
                requiere_cambio_password=bool(temp_password_detected),
            )
            session_id = session_store.create(sess, ttl_seconds=SESSION_TTL_SECONDS)
            set_session_cookie(response, session_id)
            return response
        else:
            mensaje = "Usuario o contraseña incorrectos."
    except Exception as e:
        mensaje = f"Error al validar usuario: {str(e)}"


    return templates.TemplateResponse(
        "login.html",
        {"request": request, "mensaje": mensaje, "exito": exito}
    )



# --- MODO CAMALEÓN (SIMULACIÓN / SUPLANTACIÓN DE ROLES) ---
ROLES_SICAE = {
    3: "capturista",
    4: "ceget",
    5: "titular",
    6: "analista",
    7: "jefe de departamento",
    8: "jefe de división",
    9: "directora"
}

ID_ROL_ADMINISTRADOR = 1


def _es_admin_camaleon(sess: SessionData) -> bool:
    """Verifica si la sesión tiene rol Administrador (1) o es SuperAdmin (incluso si está simulando)."""
    if not sess:
        return False
    rol_real = sess.original_id_rol if sess.is_impersonating else sess.id_rol
    if rol_real == ID_ROL_ADMINISTRADOR:
        return True
    from backend.services.usuario_service import is_super_admin
    nom = sess.original_nombre_usuario if sess.is_impersonating else sess.nombre_usuario
    apP = sess.original_apellidoP_usuario if sess.is_impersonating else sess.apellidoP_usuario
    apM = sess.original_apellidoM_usuario if sess.is_impersonating else sess.apellidoM_usuario
    return is_super_admin(nom or "", apP or "", apM or "")


def _buscar_candidatos(db: Session, id_rol: int, id_nivel: int, id_unidad: int):
    """
    Busca usuarios activos que coincidan con rol+nivel+UA.

    Reglas de filtro de nivel:
    - Rol 3 (Capturista): filtrar por Id_Nivel (pueden existir varios por UA/Nivel).
    - Roles 4 (CEGET) y 5 (Titular): son únicos por UA y tienen Id_Nivel = NULL,
      por lo que NO se filtra por nivel.
    - Roles 6-9 superiores: únicos en todo el sistema, tampoco se filtra por nivel.
    """
    from backend.database.models.Usuario import Usuario as UsuarioModel
    query = db.query(UsuarioModel).filter(
        UsuarioModel.Id_Rol == id_rol,
        UsuarioModel.Id_Unidad_Academica == id_unidad,
        UsuarioModel.Id_Estatus == 1,
    )
    # Solo el Capturista (rol 3) usa nivel como criterio de búsqueda
    if id_rol == 3 and id_nivel and id_nivel > 0:
        query = query.filter(UsuarioModel.Id_Nivel == id_nivel)
    return query.all()


def _construir_sesion_suplantada(
    current_session: SessionData,
    usuario_target,         # Objeto ORM Usuario (o None)
    rol_db,
    nivel_db,
    unidad_db,
) -> SessionData:
    """
    Construye el SessionData suplantado.
    Si usuario_target es None → solo cambia rol/nivel/UA (modo contexto previo).
    Si usuario_target existe → suplantación total de identidad.
    """
    # Respaldar identidad original (solo si no estábamos ya suplantando)
    orig_id_usuario   = current_session.original_id_usuario   if current_session.is_impersonating else current_session.id_usuario
    orig_usuario      = current_session.original_usuario      if current_session.is_impersonating else current_session.usuario
    orig_nombre       = current_session.original_nombre_usuario   if current_session.is_impersonating else current_session.nombre_usuario
    orig_apellidoP    = current_session.original_apellidoP_usuario if current_session.is_impersonating else current_session.apellidoP_usuario
    orig_apellidoM    = current_session.original_apellidoM_usuario if current_session.is_impersonating else current_session.apellidoM_usuario

    orig_rol_id       = current_session.original_id_rol              if current_session.is_impersonating else current_session.id_rol
    orig_rol_nom      = current_session.original_nombre_rol          if current_session.is_impersonating else current_session.nombre_rol
    orig_nivel_id     = current_session.original_id_nivel            if current_session.is_impersonating else current_session.id_nivel
    orig_nivel_nom    = current_session.original_nombre_nivel        if current_session.is_impersonating else current_session.nombre_nivel
    orig_unidad_id    = current_session.original_id_unidad_academica if current_session.is_impersonating else current_session.id_unidad_academica
    orig_unidad_sigla = current_session.original_sigla_unidad_academica if current_session.is_impersonating else current_session.sigla_unidad_academica

    if usuario_target:
        # --- SUPLANTACIÓN TOTAL: usar identidad real del usuario objetivo ---
        new_id_usuario        = int(usuario_target.Id_Usuario)
        new_usuario           = str(usuario_target.Usuario or "")
        new_nombre_usuario    = str(usuario_target.Nombre or "")
        new_apellidoP         = str(usuario_target.Paterno or "")
        new_apellidoM         = str(usuario_target.Materno or "")
    else:
        # --- MODO CONTEXTO: mantener identidad personal del admin ---
        new_id_usuario     = current_session.id_usuario
        new_usuario        = current_session.usuario
        new_nombre_usuario = current_session.nombre_usuario
        new_apellidoP      = current_session.apellidoP_usuario
        new_apellidoM      = current_session.apellidoM_usuario

    return SessionData(
        # Identidad activa (real del suplantado o del admin)
        id_usuario=new_id_usuario,
        usuario=new_usuario,
        nombre_usuario=new_nombre_usuario,
        apellidoP_usuario=new_apellidoP,
        apellidoM_usuario=new_apellidoM,
        requiere_cambio_password=False,

        # Nueva identidad de rol/UA/nivel
        id_rol=rol_db.Id_Rol,
        nombre_rol=rol_db.Rol,
        id_nivel=nivel_db.Id_Nivel,
        nombre_nivel=nivel_db.Nivel,
        id_unidad_academica=unidad_db.Id_Unidad_Academica,
        sigla_unidad_academica=unidad_db.Sigla,

        # Modo activo
        is_impersonating=True,

        # Respaldos de rol/UA/nivel originales
        original_id_rol=orig_rol_id,
        original_nombre_rol=orig_rol_nom,
        original_id_nivel=orig_nivel_id,
        original_nombre_nivel=orig_nivel_nom,
        original_id_unidad_academica=orig_unidad_id,
        original_sigla_unidad_academica=orig_unidad_sigla,

        # Respaldos de identidad personal originales
        original_id_usuario=orig_id_usuario,
        original_usuario=orig_usuario,
        original_nombre_usuario=orig_nombre,
        original_apellidoP_usuario=orig_apellidoP,
        original_apellidoM_usuario=orig_apellidoM,
    )


# ── GET /login/camaleon/opciones ─────────────────────────────────────────────
@router.get("/camaleon/opciones")
async def opciones_camaleon(
    current_session: SessionData = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Retorna los roles, niveles y unidades académicas activas
    para el menú del modo Camaleón.
    Solo accesible para Administrador / SuperAdmin.
    """
    from fastapi.responses import JSONResponse as _JSONResponse
    if not _es_admin_camaleon(current_session):
        return _JSONResponse(status_code=403, content={"detail": "No autorizado"})

    from backend.database.models.CatRoles import CatRoles
    from backend.database.models.CatNivel import CatNivel
    from backend.database.models.CatUnidadAcademica import CatUnidadAcademica

    roles = db.query(CatRoles).filter(CatRoles.Id_Estatus == 1).order_by(CatRoles.Id_Rol).all()
    niveles = db.query(CatNivel).filter(CatNivel.Id_Estatus == 1).order_by(CatNivel.Id_Nivel).all()
    unidades = db.query(CatUnidadAcademica).filter(CatUnidadAcademica.Id_Estatus == 1).order_by(CatUnidadAcademica.Sigla).all()

    return _JSONResponse(content={
        "ok": True,
        "roles": [
            {"id": int(r.Id_Rol), "nombre": r.Rol or f"Rol {r.Id_Rol}"}
            for r in roles
        ],
        "niveles": [
            {"id": int(n.Id_Nivel), "nombre": n.Nivel or f"Nivel {n.Id_Nivel}"}
            for n in niveles
        ],
        "unidades": [
            {
                "id": int(u.Id_Unidad_Academica),
                "sigla": u.Sigla or "",
                "nombre": u.Nombre or u.Sigla or f"UA {u.Id_Unidad_Academica}",
                "etiqueta": f"{u.Sigla} - {u.Nombre}" if (u.Sigla and u.Nombre and u.Sigla != u.Nombre) else (u.Nombre or u.Sigla)
            }
            for u in unidades
        ]
    })


# ── GET /login/candidatos-simulacion ─────────────────────────────────────────
@router.get("/candidatos-simulacion")
async def candidatos_simulacion(
    id_rol: int,
    id_nivel: int,
    id_unidad: int,
    current_session: SessionData = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Retorna la lista de usuarios activos que coinciden con rol+nivel+UA.
    Solo accesible para el Administrador.
    """
    from fastapi.responses import JSONResponse as _JSONResponse
    if not _es_admin_camaleon(current_session):
        return _JSONResponse(status_code=403, content={"detail": "No autorizado"})

    from backend.database.models.CatRoles import CatRoles
    from backend.database.models.CatNivel import CatNivel
    from backend.database.models.CatUnidadAcademica import CatUnidadAcademica

    rol_db    = db.query(CatRoles).filter(CatRoles.Id_Rol == id_rol).first()
    nivel_db  = db.query(CatNivel).filter(CatNivel.Id_Nivel == id_nivel).first()
    unidad_db = db.query(CatUnidadAcademica).filter(CatUnidadAcademica.Id_Unidad_Academica == id_unidad).first()

    if not rol_db or not nivel_db or not unidad_db:
        return _JSONResponse(status_code=404, content={"detail": "Rol, nivel o unidad no encontrada"})

    candidatos = _buscar_candidatos(db, id_rol, id_nivel, id_unidad)
    return _JSONResponse(content={
        "rol_nombre": rol_db.Rol,
        "nivel_nombre": nivel_db.Nivel,
        "unidad_sigla": unidad_db.Sigla,
        "candidatos": [
            {
                "id_usuario": int(u.Id_Usuario),
                "usuario": u.Usuario or "",
                "nombre_completo": f"{u.Nombre or ''} {u.Paterno or ''} {u.Materno or ''}".strip(),
            }
            for u in candidatos
        ]
    })


# ── POST /login/simular ───────────────────────────────────────────────────────
@router.post("/simular")
async def simular_identidad(
    request: Request,
    target_id_rol: int = Form(...),
    target_id_nivel: int = Form(...),
    target_id_unidad: int = Form(...),
    current_session: SessionData = Depends(get_current_session),
    db: Session = Depends(get_db)
):
    """
    Inicia el modo camaleón.
    • 0 candidatos → modo contexto (solo cambia rol/UA/nivel, mantiene identidad del admin)
    • 1 candidato  → suplantación automática
    • N candidatos → retorna JSON 207 con la lista para que el frontend elija
    """
    from fastapi.responses import JSONResponse as _JSONResponse
    from backend.core.security_logger import registrar_bloqueo_seguridad

    session_id = request.cookies.get("session_id")
    if not _es_admin_camaleon(current_session):
        return RedirectResponse(url="/mod_principal", status_code=303)

    from backend.database.models.CatRoles import CatRoles
    from backend.database.models.CatNivel import CatNivel
    from backend.database.models.CatUnidadAcademica import CatUnidadAcademica

    rol_db    = db.query(CatRoles).filter(CatRoles.Id_Rol == target_id_rol).first()
    nivel_db  = db.query(CatNivel).filter(CatNivel.Id_Nivel == target_id_nivel).first()
    unidad_db = db.query(CatUnidadAcademica).filter(CatUnidadAcademica.Id_Unidad_Academica == target_id_unidad).first()

    if not rol_db or not nivel_db or not unidad_db:
        return RedirectResponse(url="/mod_principal", status_code=303)

    candidatos = _buscar_candidatos(db, target_id_rol, target_id_nivel, target_id_unidad)

    # Admin que realiza la acción (siempre el original)
    admin_usuario = current_session.original_usuario if current_session.is_impersonating else current_session.usuario
    admin_nombre  = " ".join(filter(None, [
        current_session.original_nombre_usuario   if current_session.is_impersonating else current_session.nombre_usuario,
        current_session.original_apellidoP_usuario if current_session.is_impersonating else current_session.apellidoP_usuario,
        current_session.original_apellidoM_usuario if current_session.is_impersonating else current_session.apellidoM_usuario,
    ]))

    if len(candidatos) > 1:
        # N candidatos → devolver JSON 207 para que el sidebar muestre la lista
        return _JSONResponse(status_code=207, content={
            "accion": "seleccionar",
            "rol_nombre": rol_db.Rol,
            "nivel_nombre": nivel_db.Nivel,
            "unidad_sigla": unidad_db.Sigla,
            "candidatos": [
                {
                    "id_usuario": int(u.Id_Usuario),
                    "usuario": u.Usuario or "",
                    "nombre_completo": f"{u.Nombre or ''} {u.Paterno or ''} {u.Materno or ''}".strip(),
                }
                for u in candidatos
            ]
        })

    # 0 o 1 candidato → procesar directo
    usuario_target = candidatos[0] if len(candidatos) == 1 else None
    new_sess = _construir_sesion_suplantada(current_session, usuario_target, rol_db, nivel_db, unidad_db)
    session_store.update_data(session_id, new_sess)

    # ── Registro en bitácora de auditoría ────────────────────────────────────
    if usuario_target:
        nombre_suplantado = f"{usuario_target.Nombre or ''} {usuario_target.Paterno or ''} {usuario_target.Materno or ''}".strip()
        accion_log = (
            f"SUPLANTACIÓN TOTAL → usuario real: {usuario_target.Usuario} "
            f"({nombre_suplantado}) | Rol: {rol_db.Rol} | UA: {unidad_db.Sigla} | Nivel: {nivel_db.Nivel}"
        )
    else:
        accion_log = (
            f"SIMULACIÓN CONTEXTO (sin usuario real) | Rol: {rol_db.Rol} "
            f"| UA: {unidad_db.Sigla} | Nivel: {nivel_db.Nivel}"
        )
    registrar_bloqueo_seguridad(
        request=request,
        usuario_objetivo=admin_usuario,
        tipo_incidente="MODO_CAMALEON_INICIO",
        accion_tomada=f"Admin '{admin_usuario}' ({admin_nombre}) inició — {accion_log}",
        endpoint="/login/simular",
    )

    return RedirectResponse(url="/mod_principal", status_code=303)


# ── POST /login/simular-usuario ───────────────────────────────────────────────
@router.post("/simular-usuario")
async def simular_usuario_especifico(
    request: Request,
    current_session: SessionData = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Suplanta un usuario específico (por id_usuario) cuando hay varios candidatos.
    Espera JSON: { "id_usuario": int, "id_rol": int, "id_nivel": int, "id_unidad": int }
    """
    from fastapi.responses import JSONResponse as _JSONResponse
    from backend.core.security_logger import registrar_bloqueo_seguridad
    from backend.database.models.Usuario import Usuario as UsuarioModel

    if not _es_admin_camaleon(current_session):
        return _JSONResponse(status_code=403, content={"detail": "No autorizado"})

    session_id = request.cookies.get("session_id")
    body = await request.json()
    target_id_usuario = int(body.get("id_usuario", 0))
    target_id_rol     = int(body.get("id_rol", 0))
    target_id_nivel   = int(body.get("id_nivel", 0))
    target_id_unidad  = int(body.get("id_unidad", 0))

    from backend.database.models.CatRoles import CatRoles
    from backend.database.models.CatNivel import CatNivel
    from backend.database.models.CatUnidadAcademica import CatUnidadAcademica

    usuario_target = db.query(UsuarioModel).filter(
        UsuarioModel.Id_Usuario == target_id_usuario,
        UsuarioModel.Id_Estatus == 1
    ).first()
    rol_db    = db.query(CatRoles).filter(CatRoles.Id_Rol == target_id_rol).first()
    nivel_db  = db.query(CatNivel).filter(CatNivel.Id_Nivel == target_id_nivel).first()
    unidad_db = db.query(CatUnidadAcademica).filter(CatUnidadAcademica.Id_Unidad_Academica == target_id_unidad).first()

    if not usuario_target or not rol_db or not nivel_db or not unidad_db:
        return _JSONResponse(status_code=404, content={"detail": "Usuario, rol, nivel o unidad no encontrada"})

    new_sess = _construir_sesion_suplantada(current_session, usuario_target, rol_db, nivel_db, unidad_db)
    session_store.update_data(session_id, new_sess)

    # ── Registro en bitácora ──────────────────────────────────────────────────
    admin_usuario = current_session.original_usuario if current_session.is_impersonating else current_session.usuario
    admin_nombre  = " ".join(filter(None, [
        current_session.original_nombre_usuario    if current_session.is_impersonating else current_session.nombre_usuario,
        current_session.original_apellidoP_usuario if current_session.is_impersonating else current_session.apellidoP_usuario,
        current_session.original_apellidoM_usuario if current_session.is_impersonating else current_session.apellidoM_usuario,
    ]))
    nombre_suplantado = f"{usuario_target.Nombre or ''} {usuario_target.Paterno or ''} {usuario_target.Materno or ''}".strip()
    registrar_bloqueo_seguridad(
        request=request,
        usuario_objetivo=admin_usuario,
        tipo_incidente="MODO_CAMALEON_INICIO",
        accion_tomada=(
            f"Admin '{admin_usuario}' ({admin_nombre}) suplantó a {usuario_target.Usuario} "
            f"({nombre_suplantado}) | Rol: {rol_db.Rol} | UA: {unidad_db.Sigla} | Nivel: {nivel_db.Nivel}"
        ),
        endpoint="/login/simular-usuario",
    )

    return _JSONResponse(content={"ok": True, "redirect": "/mod_principal"})


# ── GET /login/restaurar-rol ──────────────────────────────────────────────────
@router.get("/restaurar-rol")
async def restaurar_rol(
    request: Request,
    current_session: SessionData = Depends(get_current_session)
):
    from backend.core.security_logger import registrar_bloqueo_seguridad

    session_id = request.cookies.get("session_id")
    if not current_session.is_impersonating:
        return RedirectResponse(url="/mod_principal", status_code=303)

    # ── Registro en bitácora antes de restaurar ───────────────────────────────
    admin_usuario = current_session.original_usuario or current_session.usuario
    admin_nombre  = " ".join(filter(None, [
        current_session.original_nombre_usuario or "",
        current_session.original_apellidoP_usuario or "",
        current_session.original_apellidoM_usuario or "",
    ]))
    registrar_bloqueo_seguridad(
        request=request,
        usuario_objetivo=admin_usuario,
        tipo_incidente="MODO_CAMALEON_FIN",
        accion_tomada=(
            f"Admin '{admin_usuario}' ({admin_nombre}) detuvo la simulación "
            f"(estaba como rol '{current_session.nombre_rol}' | UA: {current_session.sigla_unidad_academica})"
        ),
        endpoint="/login/restaurar-rol",
    )

    # ── Restaurar identidad completa del admin ────────────────────────────────
    restored = SessionData(
        # Restaurar identidad personal
        id_usuario=current_session.original_id_usuario or current_session.id_usuario,
        usuario=current_session.original_usuario or current_session.usuario,
        nombre_usuario=current_session.original_nombre_usuario or current_session.nombre_usuario,
        apellidoP_usuario=current_session.original_apellidoP_usuario or current_session.apellidoP_usuario,
        apellidoM_usuario=current_session.original_apellidoM_usuario or current_session.apellidoM_usuario,
        requiere_cambio_password=current_session.requiere_cambio_password,

        # Restaurar rol/nivel/UA originales
        id_rol=current_session.original_id_rol,
        nombre_rol=current_session.original_nombre_rol,
        id_nivel=current_session.original_id_nivel,
        nombre_nivel=current_session.original_nombre_nivel,
        id_unidad_academica=current_session.original_id_unidad_academica,
        sigla_unidad_academica=current_session.original_sigla_unidad_academica,

        # Apagar modo suplantación y limpiar respaldos
        is_impersonating=False,
        original_id_rol=None,
        original_nombre_rol=None,
        original_id_nivel=None,
        original_nombre_nivel=None,
        original_id_unidad_academica=None,
        original_sigla_unidad_academica=None,
        original_id_usuario=None,
        original_usuario=None,
        original_nombre_usuario=None,
        original_apellidoP_usuario=None,
        original_apellidoM_usuario=None,
    )

    session_store.update_data(session_id, restored)
    return RedirectResponse(url="/mod_principal", status_code=303)

