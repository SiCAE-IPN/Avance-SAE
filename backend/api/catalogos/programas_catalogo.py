"""
CRUD del catálogo de Programas Académicos (pestaña "Programas" dentro de Catálogos > Usuarios).

Usa los Stored Procedures:
  - SP_Consulta_Catalogo_Programas
  - SP_Alta_Catalogo_Programa
  - SP_Baja_Catalogo_Programa   (baja lógica: Id_Estatus = 3)

NOTA: aún no existe SP de modificación, por lo que el CRUD no expone edición.
"""
from __future__ import annotations

from fastapi import APIRouter, Request, Depends
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
from backend.services.periodo_service import get_periodo_activo, get_ultimo_periodo
from backend.services.usuario_service import is_super_admin
from backend.utils.request import get_request_host

router = APIRouter()

# Administrador (1) y Jefaturas / Dirección (7, 8, 9) pueden ver y operar el catálogo.
ROLES_PERMITIDOS_PROGRAMAS = {1, 7, 8, 9}
ID_ESTATUS_BAJA = 3


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
    """Listas para los combos del formulario (Nivel, Rama, Semestre)."""
    if not puede_gestionar_programas(sess):
        return _sin_permiso()

    niveles = db.query(CatNivel).order_by(CatNivel.Id_Nivel).all()
    ramas = db.query(CatRama).order_by(CatRama.Nombre_Rama).all()
    semestres = db.query(CatSemestre).order_by(CatSemestre.Id_Semestre).all()

    return {
        "niveles": [{"valor": n.Nivel, "etiqueta": n.Nivel} for n in niveles],
        "ramas": [{"valor": r.Nombre_Rama, "etiqueta": r.Nombre_Rama} for r in ramas],
        # El SP de alta recibe el Id_Semestre (int) y lo inserta tal cual.
        "semestres": [{"valor": s.Id_Semestre, "etiqueta": s.Semestre} for s in semestres],
    }


@router.get("/datos", response_class=JSONResponse)
def listar_programas(
    request: Request,
    sess=Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Consulta todos los programas mediante SP_Consulta_Catalogo_Programas (UA = NULL → todos)."""
    if not puede_gestionar_programas(sess):
        return _sin_permiso()

    try:
        resultado = db.execute(
            text(
                """
                SET NOCOUNT ON;
                EXEC dbo.SP_Consulta_Catalogo_Programas
                    @UUnidad_Academica = NULL,
                    @UUsuario = :UUsuario,
                    @HHost = :HHost,
                    @PPeriodo = :PPeriodo
                """
            ),
            {
                "UUsuario": _usuario_operador(sess),
                "HHost": get_request_host(request),
                "PPeriodo": _periodo_literal(db),
            },
        )
        # El SP imprime mensajes y puede emitir varios result sets: tomar el primero con filas.
        filas = []
        if not resultado.returns_rows:
            # El SP atrapa sus errores (TRY/CATCH) y termina sin result set.
            raise RuntimeError(
                "SP_Consulta_Catalogo_Programas no devolvió datos: falló internamente "
                "(revisa Bitacora: 'Error en la consulta de Programas' y que Mod_Catalogo_Programas exista en Cat_Modulo)."
            )
        cursor = resultado.cursor
        while True:
            if cursor.description:
                columnas = [c[0] for c in cursor.description]
                filas = [dict(zip(columnas, r)) for r in cursor.fetchall()]
                break
            if not cursor.nextset():
                break
        # El SP registra bitácora (INSERT) → confirmar para no dejar la transacción abierta.
        db.commit()
    except Exception as e:
        db.rollback()
        print("Error al ejecutar SP_Consulta_Catalogo_Programas:", e)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "mensaje": "No se pudo consultar el catálogo de programas."},
        )

    programas = [
        {
            "nombre": f.get("Nombre_Programa"),
            "nivel": f.get("Nivel"),
            "rama": f.get("Nombre_Rama"),
            "semestre": f.get("Semestre"),
            "estatus": f.get("Descripcion"),
        }
        for f in filas
    ]
    programas.sort(key=lambda p: (p["nombre"] or "").lower())
    return {"programas": programas}


@router.post("/alta", response_class=JSONResponse)
async def alta_programa(
    request: Request,
    sess=Depends(get_current_session),
    db: Session = Depends(get_db),
    _limit=Depends(limiter_sensible),
):
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
    if len(nombre) > 100:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "mensaje": "El nombre del programa no puede exceder 100 caracteres."},
        )

    # El SP inserta subconsultas (id_nivel / id_rama) que pueden resultar NULL y fallar en silencio;
    # por eso se valida cada valor antes de ejecutarlo.
    if not db.query(CatNivel.Id_Nivel).filter(CatNivel.Nivel == nivel).first():
        return JSONResponse(status_code=400, content={"status": "error", "mensaje": "El Nivel seleccionado no existe."})
    if not db.query(CatRama.Id_Rama).filter(CatRama.Nombre_Rama == rama).first():
        return JSONResponse(status_code=400, content={"status": "error", "mensaje": "La Rama seleccionada no existe."})
    if not db.query(CatSemestre.Id_Semestre).filter(CatSemestre.Id_Semestre == id_semestre).first():
        return JSONResponse(status_code=400, content={"status": "error", "mensaje": "El Semestre seleccionado no existe."})

    # El SP no avisa al aplicativo cuando el programa ya existe (solo hace rollback y bitácora).
    if db.query(CatProgramas.Id_Programa).filter(CatProgramas.Nombre_Programa == nombre).first():
        return JSONResponse(
            status_code=409,
            content={"status": "error", "mensaje": f"El programa '{nombre}' ya existe."},
        )

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
        print("Error al registrar programa:", e)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "mensaje": "Error al registrar el programa."},
        )

    # El SP captura sus propios errores: confirmar que realmente se insertó.
    db.expire_all()
    if not db.query(CatProgramas.Id_Programa).filter(CatProgramas.Nombre_Programa == nombre).first():
        return JSONResponse(
            status_code=500,
            content={"status": "error", "mensaje": "No se pudo registrar el programa. Revisa la bitácora."},
        )

    return {"status": "ok", "mensaje": f"Programa '{nombre}' registrado correctamente."}


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
    if programa.Id_Estatus == ID_ESTATUS_BAJA:
        return JSONResponse(
            status_code=409,
            content={"status": "error", "mensaje": f"El programa '{nombre}' está dado de baja y no puede modificarse."},
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
    if programa.Id_Estatus == ID_ESTATUS_BAJA:
        return JSONResponse(
            status_code=409,
            content={"status": "error", "mensaje": f"El programa '{nombre}' ya está dado de baja."},
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
    if not actualizado or actualizado.Id_Estatus != ID_ESTATUS_BAJA:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "mensaje": "No se pudo dar de baja el programa. Revisa la bitácora."},
        )

    return {"status": "ok", "mensaje": f"Programa '{nombre}' dado de baja correctamente."}
