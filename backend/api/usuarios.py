from __future__ import annotations

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import text
from backend.core.templates import templates
from backend.core.auth import get_current_session
from backend.core.rate_limiter import limiter_sensible
from backend.database.connection import get_db
from backend.database.models.Usuario import Usuario
from backend.services.usuario_service import (
    is_super_admin,
    has_admin_permissions,
    get_unidad_academica_nombre,
)
from backend.services.usuario_sp_service import (
    get_formatos_activos,
    get_usuarios_vista_sp,
    registrar_usuario_sp,
    modificar_usuario_sp,
    baja_usuario_sp,
)
from backend.services.roles_service import get_all_roles, get_roles_for_user_group
from backend.services.unidad_services import get_all_units
from backend.services.nivel_service import get_all_niveles
from backend.services.periodo_service import get_periodo_activo, get_ultimo_periodo
from backend.schemas.Usuario import UsuarioCreate
from sqlalchemy.orm import Session
from backend.utils.request import get_request_host
from backend.database.models.CatUnidadAcademica import CatUnidadAcademica
from backend.api.catalogos.programas_catalogo import puede_gestionar_programas

router = APIRouter()

# Definir qué roles puede crear cada rol
PERMISOS_CREACION_ROLES = {
    1: [2, 3, 4, 5, 6, 7, 8, 9],  # Rol 1 puede crear todos menos él mismo
    4: [3, 5],  # Rol 4 puede crear roles 3 y 5
    5: [3, 4],  # Rol 5 puede crear roles 3 y 4
    7: [3, 4, 5, 6, 8, 9],  # Rol 7 puede crear roles 6, 8, 9
    8: [6, 7, 9],  # Rol 8 puede crear roles 6, 7, 9
    9: [6, 7, 8],  # Rol 9 puede crear todos menos él mismo
}

ROL_CAPTURISTA = 3
ROLES_SUPERIORES_UNICOS = {6, 7, 8, 9}


def _usuario_activo_por_rol(db: Session, id_rol: int, excluir_id_usuario: int | None = None) -> Usuario | None:
    q = db.query(Usuario).filter(
        Usuario.Id_Rol == id_rol,
        Usuario.Id_Estatus == 1,
    )
    if excluir_id_usuario is not None:
        q = q.filter(Usuario.Id_Usuario != excluir_id_usuario)
    return q.first()

# Vista unificada: registro y lista de usuarios
@router.get("/", response_class=HTMLResponse)
async def usuarios_view(
    request: Request, sess=Depends(get_current_session),
    db: Session = Depends(get_db),
):
    # Datos del usuario logueado
    id_unidad_academica = int(sess.id_unidad_academica)
    id_rol = int(sess.id_rol)
    id_usuario_logueado = int(sess.id_usuario)
    Rol = str(sess.nombre_rol)
    nombre_usuario = sess.nombre_usuario
    apellidoP_usuario = sess.apellidoP_usuario
    apellidoM_usuario = sess.apellidoM_usuario
    nombre_completo = " ".join(filter(None, [nombre_usuario, apellidoP_usuario, apellidoM_usuario]))


    if id_rol == 3:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_message": "No tienes permisos para acceder a este formato.", 
            "redirect_url": "/mod_principal/",
            "session": sess
        })
    # En modo suplantación: el admin que opera NO es super admin bajo la identidad suplantada
    # Usar el nombre de la identidad activa (puede ser el suplantado o el admin en modo contexto)
    es_impersonando = bool(getattr(sess, "is_impersonating", False))
    if es_impersonando:
        # La sesión activa ya tiene los datos del suplantado → nunca es super admin
        es_super_admin = False
    else:
        es_super_admin = is_super_admin(nombre_usuario, apellidoP_usuario, apellidoM_usuario)

    # Verificar si tiene permisos administrativos
    tiene_permisos_admin = has_admin_permissions(db, id_rol)

    # Para llamar al SP de consulta de usuarios, siempre usar el login del admin REAL
    # (el SP valida permisos por login; el usuario suplantado puede no tener acceso al SP)
    if es_impersonando:
        usuario_operador = str(getattr(sess, "original_usuario", "") or getattr(sess, "usuario", "") or "sistema")
    else:
        usuario_operador = str(getattr(sess, "usuario", "") or "sistema")
    ua_obj = db.query(CatUnidadAcademica).filter(CatUnidadAcademica.Id_Unidad_Academica == id_unidad_academica).first()
    unidad_operador = ua_obj.Sigla if ua_obj else "-"
    _, periodo_literal = get_periodo_activo(db) or get_ultimo_periodo(db)
    periodo_literal = periodo_literal or ""
    host_operador = get_request_host(request)

    usuarios = get_usuarios_vista_sp(
        db,
        usuario_operador=usuario_operador,
        unidad_academica=unidad_operador,
        periodo_literal=periodo_literal,
        host=host_operador,
    )

    # CASO ESPECIAL: Roles 7, 8, 9 pueden ver usuarios de todas las UAs (como superadmin)
    if es_super_admin or id_rol in [1, 7, 8, 9]:
        nombre_ua = "Todas las Unidades Académicas"
    else:
        usuarios = [
            u
            for u in usuarios
            if int(u.get("id_unidad_academica") or 0) == id_unidad_academica
        ]
        nombre_ua = get_unidad_academica_nombre(db, id_unidad_academica)

    # FILTRO GLOBAL: NUNCA mostrar el superadmin 'admin admin admin' a nadie
    usuarios = [
        u
        for u in usuarios
        if not (
            str(u.get("nombre") or "").strip().lower() == "admin"
            and str(u.get("paterno") or "").strip().lower() == "admin"
            and str(u.get("materno") or "").strip().lower() == "admin"
        )
    ]

    # FILTRAR USUARIO ACTUAL DE LA SESIÓN (no mostrar su propio usuario en la lista)
    usuarios = [
        u for u in usuarios if int(u.get("id_usuario") or 0) != id_usuario_logueado
    ]
    
    # Filtrar roles según el grupo del rol del usuario logueado
    try:
        roles = get_roles_for_user_group(db, id_rol)
    except Exception:
        roles = get_all_roles(db)
    
    # FILTRAR ROLES DISPONIBLES según permisos del rol del usuario
    # Si es superadmin, puede ver todos los roles (excepto el suyo)
    if es_super_admin:
        roles_disponibles = [rol for rol in roles if rol.Id_Rol != id_rol]
    # Si el rol tiene permisos definidos, solo mostrar esos roles
    elif id_rol in PERMISOS_CREACION_ROLES:
        roles_permitidos = PERMISOS_CREACION_ROLES[id_rol]
        roles_disponibles = [rol for rol in roles if rol.Id_Rol in roles_permitidos]
    # Si no tiene permisos definidos, no puede crear usuarios
    else:
        roles_disponibles = []

    # Ocultar roles superiores (6-9) ya ocupados en el alta por defecto.
    roles_superiores_ocupados = {
        int(r[0])
        for r in db.query(Usuario.Id_Rol)
        .filter(Usuario.Id_Rol.in_(ROLES_SUPERIORES_UNICOS), Usuario.Id_Estatus == 1)
        .distinct()
        .all()
    }
    roles_disponibles = [
        rol for rol in roles_disponibles if rol.Id_Rol not in roles_superiores_ocupados
    ]
    
    unidades_academicas = get_all_units(db)
    niveles = get_all_niveles(db)
    formatos = get_formatos_activos(db)
    return templates.TemplateResponse(
        "usuarios.html",
        {
            "request": request,
            "usuarios": usuarios,
            "id_rol": id_rol,
            "nombre_rol": Rol or getattr(sess, "nombre_rol", ""),
            "id_unidad_academica": id_unidad_academica,
            "sigla_unidad_academica": getattr(sess, "sigla_unidad_academica", ""),
            "periodo_literal": periodo_literal,
            "nombre_ua": nombre_ua,
            "nombre_usuario": nombre_completo,
            "roles": roles_disponibles,
            "unidades_academicas": unidades_academicas,
            "niveles": niveles,
            "formatos": formatos,
            "es_super_admin": es_super_admin,
            "tiene_permisos_admin": tiene_permisos_admin,
            "puede_gestionar_programas": puede_gestionar_programas(sess),
            "rol": Rol,
            "session": sess,
        },
    )


# Endpoint para consultar formatos ya ocupados por capturistas de una UA (y opcionalmente un Nivel)
@router.get("/formatos-ocupados/{id_unidad_academica}", response_class=JSONResponse)
async def formatos_ocupados_por_ua(
    id_unidad_academica: int,
    sess=Depends(get_current_session),
    db: Session = Depends(get_db),
    id_usuario_excluir: int = None,
    id_nivel: int = None,
):
    """
    Devuelve los IDs de formatos que ya están asignados a capturistas activos
    de la Unidad Académica + Nivel indicados.
    Si id_nivel es None o 0 se ignora el filtro de nivel (comportamiento anterior).
    Opcionalmente excluye a un usuario (modo edición).
    """
    try:
        nivel_filtro = id_nivel if id_nivel and id_nivel > 0 else None
        query = text("""
            SELECT DISTINCT fu.Id_Formato
            FROM Formato_Usuario fu
            INNER JOIN Usuarios u ON u.Id_Usuario = fu.Id_Usuario
            WHERE u.Id_Unidad_Academica = :id_ua
              AND u.Id_Rol = :rol_capturista
              AND u.Id_Estatus = 1
              AND fu.Id_Estatus = 1
              AND (:excluir IS NULL OR u.Id_Usuario <> :excluir)
              AND (:id_nivel IS NULL OR u.Id_Nivel = :id_nivel)
        """)
        rows = db.execute(query, {
            "id_ua": id_unidad_academica,
            "rol_capturista": ROL_CAPTURISTA,
            "excluir": id_usuario_excluir,
            "id_nivel": nivel_filtro,
        }).mappings().all()
        ids_ocupados = [int(r["Id_Formato"]) for r in rows]
        return JSONResponse(content={"formatos_ocupados": ids_ocupados})
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})


# Endpoint para registrar usuario desde la misma página (protegido con rate limit sensible)
@router.post("/registrar", response_class=JSONResponse)
async def registrar_usuario_view(
    request: Request,
    sess=Depends(get_current_session),
    db: Session = Depends(get_db),
    _limit=Depends(limiter_sensible),
):
    data = await request.json()
    try:
        user = UsuarioCreate(**data)

        if not user.Email.endswith("@ipn.mx"):
            return JSONResponse(
                status_code=400,
                content={"detail": "El correo no cuenta con las características necesarias. Solo se permiten registros con correos @ipn.mx."}
            )

        formatos_ids = [int(x) for x in (data.get("Id_Formatos") or [])]
        if user.Id_Rol == ROL_CAPTURISTA and not formatos_ids:
            return JSONResponse(
                status_code=400,
                content={"detail": "Debes seleccionar al menos un formato."},
            )

        data["Id_Formatos"] = formatos_ids

        # VALIDACIÓN FORMATOS: Si es Capturista, verificar que ningún formato ya esté asignado
        # a otro capturista activo de la misma Unidad Académica Y mismo Nivel
        if user.Id_Rol == ROL_CAPTURISTA and formatos_ids:
            id_ua_nuevo = int(data.get("Id_Unidad_Academica") or 0)
            id_nivel_nuevo = data.get("Id_Nivel")  # puede ser None o entero
            try:
                id_nivel_nuevo = int(id_nivel_nuevo) if id_nivel_nuevo else None
            except (TypeError, ValueError):
                id_nivel_nuevo = None

            if id_ua_nuevo:
                # Construir placeholders individuales para la cláusula IN (compatible con SQL Server)
                fmt_placeholders = ", ".join(f":fmt{i}" for i in range(len(formatos_ids)))
                fmt_params = {f"fmt{i}": v for i, v in enumerate(formatos_ids)}
                fmt_params["id_ua"] = id_ua_nuevo
                fmt_params["rol_capturista"] = ROL_CAPTURISTA
                fmt_params["id_nivel"] = id_nivel_nuevo  # None si no aplica nivel
                rows_ocupados = db.execute(
                    text(f"""
                        SELECT DISTINCT fu.Id_Formato, u.Nombre, u.Paterno, u.Materno
                        FROM Formato_Usuario fu
                        INNER JOIN Usuarios u ON u.Id_Usuario = fu.Id_Usuario
                        WHERE u.Id_Unidad_Academica = :id_ua
                          AND u.Id_Rol = :rol_capturista
                          AND u.Id_Estatus = 1
                          AND fu.Id_Estatus = 1
                          AND fu.Id_Formato IN ({fmt_placeholders})
                          AND (:id_nivel IS NULL OR u.Id_Nivel = :id_nivel)
                    """),
                    fmt_params,
                ).mappings().all()

                if rows_ocupados:
                    conflictos = []
                    for r in rows_ocupados:
                        nombre_cap = f"{r['Nombre']} {r['Paterno']} {r['Materno']}".strip()
                        conflictos.append(nombre_cap)
                    nombres_unicos = ", ".join(sorted(set(conflictos)))
                    return JSONResponse(
                        status_code=400,
                        content={
                            "detail": f"Uno o más formatos seleccionados ya están asignados a otro capturista del mismo Nivel en esta Unidad Académica ({nombres_unicos}). Por favor elige solo los formatos disponibles."
                        },
                    )

        
        # Obtener datos del usuario que está registrando
        id_rol_registrador = int(sess.id_rol)
        nombre_usuario = sess.nombre_usuario
        apellidoP_usuario = sess.apellidoP_usuario
        apellidoM_usuario = sess.apellidoM_usuario
        # En suplantación, operar con los permisos del rol suplantado (nunca super admin)
        es_super_admin = False if getattr(sess, "is_impersonating", False) else is_super_admin(nombre_usuario, apellidoP_usuario, apellidoM_usuario)
        
        # VALIDACIÓN 1: Verificar que el usuario tenga permiso para crear este rol
        if not es_super_admin:
            if id_rol_registrador not in PERMISOS_CREACION_ROLES:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "No tienes permisos para crear usuarios."}
                )
            
            roles_permitidos = PERMISOS_CREACION_ROLES[id_rol_registrador]
            if user.Id_Rol not in roles_permitidos:
                return JSONResponse(
                    status_code=403,
                    content={"detail": f"No tienes permisos para crear un usuario con este rol."}
                )
        
        # VALIDACIÓN 2: Restricciones de cantidad por rol
        # Rol 4 y 5: Solo 1 por Unidad Académica
        if user.Id_Rol in [4, 5]:
            usuario_existente = db.query(Usuario).filter(
                Usuario.Id_Rol == user.Id_Rol,
                Usuario.Id_Unidad_Academica == user.Id_Unidad_Academica,
                Usuario.Id_Estatus == 1
            ).first()
            
            if usuario_existente:
                nombre_existente = f"{usuario_existente.Nombre} {usuario_existente.Paterno} {usuario_existente.Materno}".strip()
                rol_nombre = "CEGET" if user.Id_Rol == 4 else "Titular UA"
                return JSONResponse(
                    status_code=400,
                    content={
                        "detail": f"Ya existe un {rol_nombre} en esta Unidad Académica: {nombre_existente}"
                    }
                )

        # Roles superiores 6-9: solo uno activo por rol.
        if user.Id_Rol in ROLES_SUPERIORES_UNICOS:
            usuario_existente = _usuario_activo_por_rol(db, user.Id_Rol)
            if usuario_existente:
                nombre_existente = f"{usuario_existente.Nombre} {usuario_existente.Paterno} {usuario_existente.Materno}".strip()
                rol_nombres = {6: "Analista", 7: "Jefe(a) de Departamento", 8: "Jefe(a) de División", 9: "Director(a) de la DII"}
                return JSONResponse(
                    status_code=400,
                    content={
                        "detail": f"Ya existe un {rol_nombres.get(user.Id_Rol, 'usuario')} activo: {nombre_existente}"
                    }
                )

        resultado = registrar_usuario_sp(
            db,
            payload=data,
            usuario_operador=str(getattr(sess, "usuario", "") or "sistema"),
            host=get_request_host(request),
            generar_password_automatica=True,
        )

        return JSONResponse(content={"Id_Usuario": resultado["Id_Usuario"]})
    except Exception as e:
        msg = str(e)
        if "La persona ya esta registrada" in msg or "La persona ya está registrada" in msg:
            return JSONResponse(status_code=400, content={"detail": "La persona ya está registrada"})
        if "Email ya esta registrado" in msg or "Email ya está registrado" in msg:
            return JSONResponse(status_code=400, content={"detail": "Email ya está registrado"})
        return JSONResponse(status_code=400, content={"detail": msg})

# Endpoint para editar usuario desde la misma página (protegido con rate limit sensible)
@router.post("/editar/{id_usuario}", response_class=JSONResponse)
async def editar_usuario_ajax(
    id_usuario: int,
    request: Request,
    sess=Depends(get_current_session),
    db: Session = Depends(get_db),
    _limit=Depends(limiter_sensible),
):
    try:
        data = await request.json()
        
        email = data.get("Email")
        if email and not email.endswith("@ipn.mx"):
            return JSONResponse(
                status_code=400,
                content={"mensaje": "El correo no cuenta con las características necesarias. Solo se permiten correos @ipn.mx."}
            )
        formatos_ids = [int(x) for x in (data.get("Id_Formatos") or [])]
        data["Id_Formatos"] = formatos_ids
        
        # Obtener datos del usuario que está editando
        id_rol_editor = int(sess.id_rol)
        nombre_usuario = sess.nombre_usuario
        apellidoP_usuario = sess.apellidoP_usuario
        apellidoM_usuario = sess.apellidoM_usuario
        # En suplantación, operar con los permisos del rol suplantado (nunca super admin)
        es_super_admin = False if getattr(sess, "is_impersonating", False) else is_super_admin(nombre_usuario, apellidoP_usuario, apellidoM_usuario)
        
        # Obtener el usuario actual para comparar
        usuario_actual = db.query(Usuario).filter(Usuario.Id_Usuario == id_usuario).first()
        if not usuario_actual:
            return JSONResponse(
                status_code=404,
                content={"mensaje": "Usuario no encontrado."}
            )

        nuevo_id_rol = int(data.get("Id_Rol") or usuario_actual.Id_Rol)
        nueva_id_unidad = int(data.get("Id_Unidad_Academica") or usuario_actual.Id_Unidad_Academica)

        if nuevo_id_rol == ROL_CAPTURISTA and not formatos_ids:
            return JSONResponse(
                status_code=400,
                content={"mensaje": "Debes seleccionar al menos un formato."},
            )
        
        # VALIDACIÓN 1: Verificar que el usuario tenga permiso para asignar este rol
        if not es_super_admin:
            if id_rol_editor not in PERMISOS_CREACION_ROLES:
                return JSONResponse(
                    status_code=403,
                    content={"mensaje": "No tienes permisos para editar usuarios."}
                )
            
            roles_permitidos = PERMISOS_CREACION_ROLES[id_rol_editor]
            if nuevo_id_rol not in roles_permitidos:
                return JSONResponse(
                    status_code=403,
                    content={"mensaje": "No tienes permisos para asignar este rol."}
                )
        
        # VALIDACIÓN 2: Si cambió el rol, verificar restricciones de cantidad
        if nuevo_id_rol != usuario_actual.Id_Rol:
            # Rol 4 y 5: Solo 1 por Unidad Académica
            if nuevo_id_rol in [4, 5]:
                usuario_existente = db.query(Usuario).filter(
                    Usuario.Id_Rol == nuevo_id_rol,
                    Usuario.Id_Unidad_Academica == nueva_id_unidad,
                    Usuario.Id_Estatus == 1,
                    Usuario.Id_Usuario != id_usuario
                ).first()
                
                if usuario_existente:
                    nombre_existente = f"{usuario_existente.Nombre} {usuario_existente.Paterno} {usuario_existente.Materno}".strip()
                    rol_nombre = "CEGET" if nuevo_id_rol == 4 else "Titular UA"
                    return JSONResponse(
                        status_code=400,
                        content={
                            "mensaje": f"Ya existe un {rol_nombre} en esta Unidad Académica: {nombre_existente}"
                        }
                    )

            # Roles superiores 6-9: solo uno activo por rol.
            if nuevo_id_rol in ROLES_SUPERIORES_UNICOS:
                usuario_existente = _usuario_activo_por_rol(db, nuevo_id_rol, excluir_id_usuario=id_usuario)
                if usuario_existente:
                    nombre_existente = f"{usuario_existente.Nombre} {usuario_existente.Paterno} {usuario_existente.Materno}".strip()
                    rol_nombres = {6: "Analista", 7: "Jefe/a de División", 8: "Titular", 9: "Administrador General"}
                    return JSONResponse(
                        status_code=400,
                        content={
                            "mensaje": f"Ya existe un {rol_nombres.get(nuevo_id_rol, 'usuario')} activo: {nombre_existente}"
                        }
                    )

        modificar_usuario_sp(
            db,
            id_usuario=id_usuario,
            payload=data,
            usuario_operador=str(getattr(sess, "usuario", "") or "sistema"),
            host=get_request_host(request),
        )

        return JSONResponse(content={"mensaje": "Usuario actualizado correctamente."})
    except ValueError as e:
        return JSONResponse(content={"mensaje": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse(content={"mensaje": str(e)}, status_code=500)

# Baja lógica de usuario (Id_Estatus = 3, protegido con rate limit sensible)
@router.post("/eliminar/{id_usuario}", response_class=JSONResponse)
async def eliminar_usuario(
    id_usuario: int,
    request: Request,
    sess=Depends(get_current_session),
    db: Session = Depends(get_db),
    _limit=Depends(limiter_sensible),
):
    id_rol = int(sess.id_rol)
    nombre_usuario = sess.nombre_usuario
    apellidoP_usuario = sess.apellidoP_usuario
    apellidoM_usuario = sess.apellidoM_usuario
    # En suplantación, operar con los permisos del rol suplantado (nunca super admin)
    es_super = False if getattr(sess, "is_impersonating", False) else is_super_admin(nombre_usuario, apellidoP_usuario, apellidoM_usuario)
    if not es_super and id_rol not in PERMISOS_CREACION_ROLES:
        return JSONResponse(status_code=403, content={"mensaje": "No tienes permisos para dar de baja usuarios."})

    try:
        baja_usuario_sp(
            db,
            id_usuario=id_usuario,
            usuario_operador=str(getattr(sess, "usuario", "") or "sistema"),
            host=get_request_host(request),
        )

        return JSONResponse(content={"mensaje": "Usuario dado de baja correctamente."})
    except ValueError as e:
        msg = str(e)
        status = 404 if "no encontrado" in msg.lower() else 400
        return JSONResponse(content={"mensaje": msg}, status_code=status)
    except Exception as e:
        return JSONResponse(content={"mensaje": str(e)}, status_code=500)
