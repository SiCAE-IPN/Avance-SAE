"""
CRUD del catálogo de Programas Académicos (pestaña "Programas" dentro de Catálogos > Usuarios).

Usa los Stored Procedures:
  - SP_Consulta_Catalogo_Programas
  - SP_Alta_Catalogo_Programa
  - SP_Baja_Catalogo_Programa   (baja lógica: Id_Estatus = 3)

NOTA: aún no existe SP de modificación, por lo que el CRUD no expone edición.
"""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.core.auth import get_current_session
from backend.core.rate_limiter import limiter_sensible
from backend.database.connection import get_db
from backend.database.models.CatProgramas import CatProgramas
from backend.database.models.CatNivel import CatNivel
from backend.database.models.CatRama import CatRama
from backend.database.models.CatSemestre import CatSemestre
from backend.database.models.CatUnidadAcademica import CatUnidadAcademica
from backend.database.models.CatModalidad import CatModalidad
from backend.database.models.CatEstatus import CatEstatus
from backend.services.periodo_service import get_periodo_activo, get_ultimo_periodo
from backend.services.usuario_service import is_super_admin
from backend.utils.request import get_request_host

router = APIRouter()

# Administrador (1) y Jefaturas / Dirección (7, 8, 9) pueden ver y operar el catálogo.
ROLES_PERMITIDOS_PROGRAMAS = {1, 7, 8, 9}
ID_ESTATUS_ACTIVO = 1
ID_ESTATUS_INACTIVO = 2
ID_ESTATUS_ELIMINADO = 3
ESTATUS_INACTIVOS = {ID_ESTATUS_INACTIVO, ID_ESTATUS_ELIMINADO}


def puede_gestionar_programas(sess) -> bool:
    """True si la sesión activa puede ver/operar el catálogo de programas."""
    try:
        id_rol = int(getattr(sess, "id_rol", 0) or 0)
    except (TypeError, ValueError):
        return False
    if id_rol in ROLES_PERMITIDOS_PROGRAMAS:
        return True
    if getattr(sess, "is_impersonating", False):
        return False
    return is_super_admin(
        getattr(sess, "nombre_usuario", "") or "",
        getattr(sess, "apellidoP_usuario", "") or "",
        getattr(sess, "apellidoM_usuario", "") or "",
    )


def _sin_permiso() -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"status": "error", "mensaje": "No tienes permisos para realizar esta acción."},
    )


def _periodo_literal(db: Session) -> str:
    _, periodo = get_periodo_activo(db) or get_ultimo_periodo(db)
    return periodo or ""


def _usuario_operador(sess) -> str:
    return str(getattr(sess, "usuario", "") or "sistema")


@router.get("/opciones", response_class=JSONResponse)
def opciones_programas(sess=Depends(get_current_session), db: Session = Depends(get_db)):
    """Listas para los combos del formulario y filtros (Nivel, Rama, Semestre, UA, Modalidad)."""
    if not puede_gestionar_programas(sess):
        return _sin_permiso()

    niveles = db.query(CatNivel).order_by(CatNivel.Id_Nivel).all()
    ramas = db.query(CatRama).order_by(CatRama.Nombre_Rama).all()
    semestres = db.query(CatSemestre).order_by(CatSemestre.Id_Semestre).all()
    unidades = db.query(CatUnidadAcademica).order_by(CatUnidadAcademica.Sigla).all()
    modalidades = db.query(CatModalidad).order_by(CatModalidad.Modalidad).all()

    ua_usuario = getattr(sess, "sigla_unidad_academica", "") or ""
    nivel_usuario = getattr(sess, "nombre_nivel", "") or ""

    return {
        "niveles": [{"valor": n.Nivel, "etiqueta": n.Nivel} for n in niveles],
        "ramas": [{"valor": r.Nombre_Rama, "etiqueta": r.Nombre_Rama} for r in ramas],
        "semestres": [{"valor": s.Id_Semestre, "etiqueta": s.Semestre} for s in semestres],
        "unidades": [{"valor": u.Sigla, "etiqueta": u.Sigla, "nombre": u.Nombre} for u in unidades],
        "modalidades": [{"valor": m.Modalidad, "etiqueta": m.Modalidad} for m in modalidades],
        "usuario_ua": ua_usuario,
        "usuario_nivel": nivel_usuario,
    }


@router.get("/datos", response_class=JSONResponse)
def listar_programas(
    request: Request,
    unidad: Optional[str] = Query(None),
    nivel: Optional[str] = Query(None),
    sess=Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Consulta de programas:
    - Si se especifica Unidad Académica (y opcionalmente Nivel), usa SP_Consulta_Programa_Modalidad.
    - Si no se especifica Unidad, consulta el catálogo general mediante SP_Consulta_Catalogo_Programas.
    """
    if not puede_gestionar_programas(sess):
        return _sin_permiso()

    filas = []
    unidad_limpia = (unidad or "").strip()
    nivel_limpio = (nivel or "").strip()

    # Preparamos un diccionario con rama y estatus de CatProgramas para complementar columnas
    try:
        ramas_dict = {r.Id_Rama: r.Nombre_Rama for r in db.query(CatRama).all()}
        estatus_dict = {e.Id_Estatus: e.Descripcion for e in db.query(CatEstatus).all()}
        progs_catalogo = db.query(CatProgramas).all()
        prog_meta = {
            p.Nombre_Programa.strip().lower(): {
                "rama": ramas_dict.get(p.Id_Rama_Programa, ""),
                "estatus": estatus_dict.get(p.Id_Estatus, "Activo"),
            }
            for p in progs_catalogo if p.Nombre_Programa
        }
    except Exception:
        prog_meta = {}

    try:
        if unidad_limpia:
            # Si se indicó nivel específico, consultamos ese nivel; si no, consultamos los niveles disponibles
            niveles_a_consultar = [nivel_limpio] if nivel_limpio else ["Medio Superior", "Superior", "Posgrado"]
            for niv in niveles_a_consultar:
                resultado = db.execute(
                    text(
                        """
                        SET NOCOUNT ON;
                        EXEC dbo.SP_Consulta_Programa_Modalidad
                            @UUnidad_Academica = :UUnidad_Academica,
                            @NNivel = :NNivel,
                            @UUsuario = :UUsuario,
                            @HHost = :HHost,
                            @PPeriodo = :PPeriodo
                        """
                    ),
                    {
                        "UUnidad_Academica": unidad_limpia,
                        "NNivel": niv,
                        "UUsuario": _usuario_operador(sess),
                        "HHost": get_request_host(request),
                        "PPeriodo": _periodo_literal(db),
                    },
                )
                if resultado.returns_rows and resultado.cursor:
                    cursor = resultado.cursor
                    while True:
                        if cursor.description:
                            cols = [c[0] for c in cursor.description]
                            for r in cursor.fetchall():
                                filas.append(dict(zip(cols, r)))
                            break
                        if not cursor.nextset():
                            break
            db.commit()

            programas = [
                {
                    "unidad": f.get("sigla") or f.get("Sigla") or unidad_limpia,
                    "nombre": f.get("Nombre_Programa"),
                    "modalidad": f.get("Modalidad") or "",
                    "nivel": f.get("Nivel") or "",
                    "rama": prog_meta.get(str(f.get("Nombre_Programa") or "").strip().lower(), {}).get("rama", ""),
                    "semestre": f.get("id_semestre") or f.get("Semestre") or "",
                    "estatus": prog_meta.get(str(f.get("Nombre_Programa") or "").strip().lower(), {}).get("estatus", "Activo"),
                }
                for f in filas
            ]
        else:
            # Consulta general completa: relaciona todos los programas con su Unidad Académica y Modalidad
            sql_general = """
                SELECT 
                    ISNULL(ua.Sigla, '') AS unidad,
                    pro.Nombre_Programa AS nombre,
                    ISNULL(md.Modalidad, '') AS modalidad,
                    ISNULL(niv.Nivel, '') AS nivel,
                    ISNULL(ram.Nombre_Rama, '') AS rama,
                    ISNULL(sem.Semestre, '') AS semestre,
                    ISNULL(est.Descripcion, 'Activo') AS estatus
                FROM [dbo].[Cat_programas] pro WITH (NOLOCK)
                LEFT JOIN [dbo].[Programa_Modalidad] pm WITH (NOLOCK) ON pm.Id_Programa = pro.Id_Programa
                LEFT JOIN [dbo].[Cat_Modalidad] md WITH (NOLOCK) ON md.Id_Modalidad = pm.Id_Modalidad
                LEFT JOIN [dbo].[Unidad_Programa_Modalidad] upm WITH (NOLOCK) ON upm.Id_Modalidad_Programa = pm.Id_Modalidad_Programa
                LEFT JOIN [dbo].[Cat_Unidad_Academica] ua WITH (NOLOCK) ON ua.Id_Unidad_Academica = upm.Id_Unidad_Academica
                LEFT JOIN [dbo].[Cat_Nivel] niv WITH (NOLOCK) ON pro.Id_Nivel = niv.Id_Nivel
                LEFT JOIN [dbo].[Cat_Rama] ram WITH (NOLOCK) ON pro.Id_Rama_Programa = ram.Id_Rama
                LEFT JOIN [dbo].[Cat_Semestre] sem WITH (NOLOCK) ON pro.Id_Semestre = sem.Id_Semestre
                LEFT JOIN [dbo].[Cat_Estatus] est WITH (NOLOCK) ON pro.Id_Estatus = est.Id_Estatus
                WHERE (:NNivel IS NULL OR :NNivel = '' OR niv.Nivel = :NNivel)
                ORDER BY 
                    CASE WHEN ua.Sigla IS NULL OR ua.Sigla = '' THEN 1 ELSE 0 END,
                    ua.Sigla, 
                    pro.Nombre_Programa, 
                    md.Modalidad
            """
            rows = db.execute(text(sql_general), {"NNivel": nivel_limpio or None}).fetchall()
            programas = [
                {
                    "unidad": r[0] or "",
                    "nombre": r[1] or "",
                    "modalidad": r[2] or "",
                    "nivel": r[3] or "",
                    "rama": r[4] or "",
                    "semestre": r[5] or "",
                    "estatus": r[6] or "Activo",
                }
                for r in rows
            ]

    except Exception as e:
        db.rollback()
        print("Error al consultar programas:", e)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "mensaje": "No se pudo consultar el catálogo de programas."},
        )

    programas.sort(key=lambda p: (0 if p.get("unidad") else 1, p.get("unidad") or "", (p.get("nombre") or "").lower()))
    return {"programas": programas}


@router.post("/alta", response_class=JSONResponse)
async def alta_programa(
    request: Request,
    sess=Depends(get_current_session),
    db: Session = Depends(get_db),
    _limit=Depends(limiter_sensible),
):
    """
    Alta de programa:
    1. Si no existe en Cat_programas, se registra con SP_Alta_Catalogo_Programa.
    2. Se vincula con Unidad Académica y Modalidad mediante SP_Alta_Programa_Modalidad_Con_Validacion.
    3. Se valida el resultado y se devuelven los mensajes diagnósticos de bitácora.
    """
    if not puede_gestionar_programas(sess):
        return _sin_permiso()

    data = await request.json()
    nombre = str(data.get("nombre") or "").strip()
    nivel = str(data.get("nivel") or "").strip()
    rama = str(data.get("rama") or "").strip()
    unidad = str(data.get("unidad") or "").strip()
    modalidad = str(data.get("modalidad") or "").strip()
    try:
        id_semestre = int(data.get("semestre"))
    except (TypeError, ValueError):
        id_semestre = None

    if not nombre or not nivel or not rama or not unidad or not modalidad or id_semestre is None:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "mensaje": "Nombre, Nivel, Rama, Semestre, Unidad Académica y Modalidad son obligatorios."},
        )
    if len(nombre) > 100:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "mensaje": "El nombre del programa no puede exceder 100 caracteres."},
        )

    # Validaciones contra catálogos
    if not db.query(CatNivel.Id_Nivel).filter(CatNivel.Nivel == nivel).first():
        return JSONResponse(status_code=400, content={"status": "error", "mensaje": "El Nivel seleccionado no existe."})
    if not db.query(CatRama.Id_Rama).filter(CatRama.Nombre_Rama == rama).first():
        return JSONResponse(status_code=400, content={"status": "error", "mensaje": "La Rama seleccionada no existe."})
    if not db.query(CatSemestre.Id_Semestre).filter(CatSemestre.Id_Semestre == id_semestre).first():
        return JSONResponse(status_code=400, content={"status": "error", "mensaje": "El Semestre seleccionado no existe."})
    if not db.query(CatUnidadAcademica.Id_Unidad_Academica).filter(
        (CatUnidadAcademica.Sigla == unidad) | (CatUnidadAcademica.Nombre == unidad)
    ).first():
        return JSONResponse(status_code=400, content={"status": "error", "mensaje": "La Unidad Académica seleccionada no existe."})
    if not db.query(CatModalidad.Id_Modalidad).filter(CatModalidad.Modalidad == modalidad).first():
        return JSONResponse(status_code=400, content={"status": "error", "mensaje": "La Modalidad seleccionada no existe."})

    # Paso 1: Registrar en Cat_programas si aún no existe
    existe_en_catalogo = db.query(CatProgramas.Id_Programa).filter(CatProgramas.Nombre_Programa == nombre).first()
    if not existe_en_catalogo:
        try:
            db.execute(
                text(
                    """
                    EXEC [dbo].[SP_Alta_Catalogo_Programa]
                        @PPrograma = :PPrograma,
                        @RRama = :RRama,
                        @NNivel = :NNivel,
                        @SSemestre = :SSemestre,
                        @UUsuario = :UUsuario,
                        @HHost = :HHost,
                        @PPeriodo = :PPeriodo
                    """
                ),
                {
                    "PPrograma": nombre,
                    "RRama": rama,
                    "NNivel": nivel,
                    "SSemestre": id_semestre,
                    "UUsuario": _usuario_operador(sess),
                    "HHost": get_request_host(request),
                    "PPeriodo": _periodo_literal(db),
                },
            )
            db.commit()
        except Exception as e:
            db.rollback()
            print("Error al registrar en Cat_programas:", e)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "mensaje": f"Error al registrar el programa en el catálogo general: {e}"},
            )

        db.expire_all()
        if not db.query(CatProgramas.Id_Programa).filter(CatProgramas.Nombre_Programa == nombre).first():
            return JSONResponse(
                status_code=500,
                content={"status": "error", "mensaje": "No se pudo registrar el programa en Cat_programas. Revisa la bitácora."},
            )

    # Paso 2: Ejecutar SP_Alta_Programa_Modalidad_Con_Validacion para ligarlo con la UA y la Modalidad
    params_modalidad = {
        "UUnidad_Academica": unidad,
        "PPeriodo": _periodo_literal(db),
        "NNivel": nivel,
        "PPrograma": nombre,
        "MModalidad": modalidad,
        "UUsuario": _usuario_operador(sess),
        "HHost": get_request_host(request),
    }

    print("\n" + "=" * 60)
    print(">>> Ejecutando SP_Alta_Programa_Modalidad_Con_Validacion con los siguientes valores:")
    for k, v in params_modalidad.items():
        print(f"    @{k} = {v!r}")
    print("=" * 60 + "\n")

    try:
        resultado_sp = db.execute(
            text(
                """
                SET NOCOUNT ON;
                EXEC [dbo].[SP_Alta_Programa_Modalidad_Con_Validacion]
                    @UUnidad_Academica = :UUnidad_Academica,
                    @PPeriodo = :PPeriodo,
                    @NNivel = :NNivel,
                    @PPrograma = :PPrograma,
                    @MModalidad = :MModalidad,
                    @UUsuario = :UUsuario,
                    @HHost = :HHost
                """
            ),
            params_modalidad,
        )
        # El SP devuelve (ERROR_NUMBER, ERROR_MESSAGE, ERROR_LINE) en su CATCH: capturarlo.
        error_sp = None
        if resultado_sp.returns_rows and resultado_sp.cursor:
            try:
                while True:
                    filas = resultado_sp.cursor.fetchall()
                    if filas and len(filas[0]) >= 3 and error_sp is None:
                        error_sp = f"Error SQL {filas[0][0]} (línea {filas[0][2]}): {filas[0][1]}"
                    if not resultado_sp.cursor.nextset():
                        break
            except Exception:
                pass
        db.commit()
    except Exception as e:
        db.rollback()
        print("Error al ejecutar SP_Alta_Programa_Modalidad_Con_Validacion:", e)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "mensaje": f"Error al ejecutar SP_Alta_Programa_Modalidad_Con_Validacion: {e}"},
        )

    # Paso 3: Verificar si el SP insertó la relación en Unidad_Programa_Modalidad
    db.expire_all()
    rel_existe = db.execute(
        text(
            """
            SELECT COUNT(*)
            FROM [dbo].[Cat_Unidad_Academica] ua
            INNER JOIN [dbo].[Unidad_Programa_Modalidad] upm ON upm.Id_Unidad_Academica = ua.Id_Unidad_Academica
            INNER JOIN [dbo].[Programa_Modalidad] pm ON pm.Id_Modalidad_Programa = upm.Id_Modalidad_Programa
            INNER JOIN [dbo].[Cat_Modalidad] md ON md.Id_Modalidad = pm.Id_Modalidad
            INNER JOIN [dbo].[Cat_programas] pro ON pro.Id_Programa = pm.Id_Programa
            WHERE (ua.Sigla = :ua OR ua.Nombre = :ua)
              AND md.Modalidad = :mod
              AND pro.Nombre_Programa = :prog
            """
        ),
        {"ua": unidad, "mod": modalidad, "prog": nombre},
    ).scalar()

    # Consultar mensaje en Bitacora
    bit_row = db.execute(
        text(
            """
            SELECT TOP 1 Acciones
            FROM [dbo].[Bitacora]
            WHERE Host = :h
            ORDER BY Id_Bitacora DESC
            """
        ),
        {"h": get_request_host(request)},
    ).scalar()

    if rel_existe and rel_existe > 0:
        return {"status": "ok", "mensaje": f"Programa '{nombre}' registrado y vinculado a {unidad} ({modalidad}) correctamente."}
    else:
        # Si no se insertó la relación, informamos detalladamente al frontend
        return JSONResponse(
            status_code=400,
            content={
                "status": "warning",
                "mensaje": (
                    f"El programa '{nombre}' se guardó en el catálogo general, pero SP_Alta_Programa_Modalidad_Con_Validacion "
                    f"no insertó la relación en la base de datos. Detalle de Bitácora del SP: '{bit_row or 'Sin registro'}'."
                    + (f" {error_sp}" if error_sp else "")
                ),
            },
        )


@router.post("/modificar", response_class=JSONResponse)
async def modificar_programa(
    request: Request,
    sess=Depends(get_current_session),
    db: Session = Depends(get_db),
    _limit=Depends(limiter_sensible),
):
    """
    Modifica Nivel, Rama y Semestre de un programa existente.
    El SP identifica el programa por su nombre, por lo que el nombre no es editable.
    """
    if not puede_gestionar_programas(sess):
        return _sin_permiso()

    data = await request.json()
    nombre = str(data.get("nombre") or "").strip()
    nivel = str(data.get("nivel") or "").strip()
    rama = str(data.get("rama") or "").strip()
    try:
        id_semestre = int(data.get("semestre"))
    except (TypeError, ValueError):
        id_semestre = None

    if not nombre or not nivel or not rama or id_semestre is None:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "mensaje": "Nombre, Nivel, Rama y Semestre son obligatorios."},
        )

    # El SP asigna subconsultas que pueden resultar NULL; validar antes de ejecutarlo.
    nivel_row = db.query(CatNivel.Id_Nivel).filter(CatNivel.Nivel == nivel).first()
    if not nivel_row:
        return JSONResponse(status_code=400, content={"status": "error", "mensaje": "El Nivel seleccionado no existe."})
    rama_row = db.query(CatRama.Id_Rama).filter(CatRama.Nombre_Rama == rama).first()
    if not rama_row:
        return JSONResponse(status_code=400, content={"status": "error", "mensaje": "La Rama seleccionada no existe."})
    if not db.query(CatSemestre.Id_Semestre).filter(CatSemestre.Id_Semestre == id_semestre).first():
        return JSONResponse(status_code=400, content={"status": "error", "mensaje": "El Semestre seleccionado no existe."})

    programa = db.query(CatProgramas).filter(CatProgramas.Nombre_Programa == nombre).first()
    if not programa:
        return JSONResponse(
            status_code=404,
            content={"status": "error", "mensaje": f"El programa '{nombre}' no existe."},
        )
    if programa.Id_Estatus in ESTATUS_INACTIVOS:
        return JSONResponse(
            status_code=409,
            content={"status": "error", "mensaje": f"El programa '{nombre}' está inactivo y no puede modificarse."},
        )

    id_nivel, id_rama = int(nivel_row[0]), int(rama_row[0])
    if (programa.Id_Nivel, programa.Id_Rama_Programa, programa.Id_Semestre) == (id_nivel, id_rama, id_semestre):
        return JSONResponse(
            status_code=400,
            content={"status": "error", "mensaje": "No hay cambios que guardar."},
        )

    try:
        db.execute(
            text(
                """
                EXEC [dbo].[SP_Modifica_Catalogo_Programa]
                    @PPrograma = :PPrograma,
                    @RRama = :RRama,
                    @NNivel = :NNivel,
                    @SSemestre = :SSemestre,
                    @UUsuario = :UUsuario,
                    @HHost = :HHost,
                    @PPeriodo = :PPeriodo
                """
            ),
            {
                "PPrograma": nombre,
                "RRama": rama,
                "NNivel": nivel,
                "SSemestre": id_semestre,
                "UUsuario": _usuario_operador(sess),
                "HHost": get_request_host(request),
                "PPeriodo": _periodo_literal(db),
            },
        )
        db.commit()
    except Exception as e:
        db.rollback()
        print("Error al modificar programa:", e)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "mensaje": "Error al modificar el programa."},
        )

    # El SP captura sus propios errores: confirmar que el cambio se aplicó.
    db.expire_all()
    actualizado = db.query(CatProgramas).filter(CatProgramas.Nombre_Programa == nombre).first()
    if not actualizado or (actualizado.Id_Nivel, actualizado.Id_Rama_Programa, actualizado.Id_Semestre) != (id_nivel, id_rama, id_semestre):
        return JSONResponse(
            status_code=500,
            content={"status": "error", "mensaje": "No se pudo modificar el programa. Revisa la bitácora."},
        )

    return {"status": "ok", "mensaje": f"Programa '{nombre}' modificado correctamente."}


@router.post("/baja", response_class=JSONResponse)
async def baja_programa(
    request: Request,
    sess=Depends(get_current_session),
    db: Session = Depends(get_db),
    _limit=Depends(limiter_sensible),
):
    if not puede_gestionar_programas(sess):
        return _sin_permiso()

    data = await request.json()
    nombre = str(data.get("nombre") or "").strip()
    if not nombre:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "mensaje": "Debes indicar el programa a dar de baja."},
        )

    programa = db.query(CatProgramas).filter(CatProgramas.Nombre_Programa == nombre).first()
    if not programa:
        return JSONResponse(
            status_code=404,
            content={"status": "error", "mensaje": f"El programa '{nombre}' no existe."},
        )
    if programa.Id_Estatus in ESTATUS_INACTIVOS:
        return JSONResponse(
            status_code=409,
            content={"status": "error", "mensaje": f"El programa '{nombre}' ya está inactivo."},
        )

    try:
        db.execute(
            text(
                """
                EXEC [dbo].[SP_Baja_Catalogo_Programa]
                    @PPrograma = :PPrograma,
                    @UUsuario = :UUsuario,
                    @HHost = :HHost
                """
            ),
            {
                "PPrograma": nombre,
                "UUsuario": _usuario_operador(sess),
                "HHost": get_request_host(request),
            },
        )
        db.commit()
    except Exception as e:
        db.rollback()
        print("Error al dar de baja programa:", e)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "mensaje": "Error al dar de baja el programa."},
        )

    db.expire_all()
    actualizado = db.query(CatProgramas).filter(CatProgramas.Nombre_Programa == nombre).first()
    if not actualizado or actualizado.Id_Estatus not in ESTATUS_INACTIVOS:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "mensaje": "No se pudo dar de baja el programa. Revisa la bitácora."},
        )

    return {"status": "ok", "mensaje": f"Programa '{nombre}' dado de baja correctamente."}
