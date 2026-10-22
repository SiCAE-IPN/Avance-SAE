"""
Panel de Validación Central (roles 6-9: Analista, Jefe/a de Departamento,
Jefe/a de División y Director/a de la DII).

Este router SOLO aporta los datos de lectura que necesita la nueva vista
(catálogo Nivel -> Unidad Académica y estado de cada módulo). La validación y el
rechazo siguen ejecutándose con los endpoints (y SPs) existentes de cada módulo:

    Matrícula         -> /matricula/validar_semestre_rol  | /matricula/rechazar_semestre_rol
    Aprovechamiento   -> /aprovechamiento/validar         | /aprovechamiento/rechazar
    Egresados         -> /egresados/validar               | /egresados/rechazar
    Titulados         -> /titulados/validar               | /titulados/rechazar

El periodo que se envía siempre es el periodo ACTIVO.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.core.auth import get_current_session
from backend.database.connection import get_db
from backend.database.models.CatNivel import CatNivel as Nivel
from backend.database.models.CatPeriodo import CatPeriodo
from backend.database.models.CatRoles import CatRoles
from backend.database.models.CatSemaforo import CatSemaforo
from backend.database.models.CatUnidadAcademica import CatUnidadAcademica as Unidad_Academica
from backend.database.models.SemaforoUnidadAcademica import SemaforoUnidadAcademica
from backend.services.periodo_service import get_periodo_activo, get_periodo_anterior_al_ultimo

router = APIRouter()

ROLES_VALIDACION_CENTRAL = (6, 7, 8, 9)

# (Id_Formato, clave de módulo, etiqueta)
MODULOS = [
    (1, "matricula", "Matrícula"),
    (2, "aprovechamiento", "Aprovechamiento Académico"),
    (3, "egresados", "Egresados"),
    (4, "titulados", "Titulados"),
]


def _exigir_rol(sess) -> int:
    id_rol = int(getattr(sess, "id_rol", 0) or 0)
    if id_rol not in ROLES_VALIDACION_CENTRAL:
        raise HTTPException(
            status_code=403,
            detail="Solo los roles 6 al 9 pueden usar el panel de validación.",
        )
    return id_rol


def _periodo_activo(db: Session):
    periodo_id, periodo_literal = get_periodo_activo(db)
    if not periodo_id or not periodo_literal:
        raise HTTPException(status_code=404, detail="No hay un periodo activo configurado.")
    return int(periodo_id), str(periodo_literal)


@router.get("/catalogo", response_class=JSONResponse)
def catalogo_validacion(sess=Depends(get_current_session), db: Session = Depends(get_db)):
    """Niveles con sus Unidades Académicas (derivado de Semaforo_Unidad_Academica)."""
    _exigir_rol(sess)
    _, periodo_literal = _periodo_activo(db)

    filas = (
        db.query(Unidad_Academica, SemaforoUnidadAcademica.Id_Nivel)
        .join(
            SemaforoUnidadAcademica,
            Unidad_Academica.Id_Unidad_Academica == SemaforoUnidadAcademica.Id_Unidad_Academica,
        )
        .filter(Unidad_Academica.Id_Estatus == 1)
        .distinct()
        .order_by(Unidad_Academica.Nombre)
        .all()
    )

    unidades_por_nivel: dict[int, dict[int, dict]] = {}
    for ua, id_nivel in filas:
        if id_nivel is None:
            continue
        unidades_por_nivel.setdefault(int(id_nivel), {})[int(ua.Id_Unidad_Academica)] = {
            "id": int(ua.Id_Unidad_Academica),
            "sigla": ua.Sigla,
            "nombre": ua.Nombre,
        }

    niveles = []
    for nivel in db.query(Nivel).filter(Nivel.Id_Estatus == 1).order_by(Nivel.Id_Nivel).all():
        unidades = sorted(
            unidades_por_nivel.get(int(nivel.Id_Nivel), {}).values(),
            key=lambda u: (u["nombre"] or ""),
        )
        niveles.append({"id": int(nivel.Id_Nivel), "nombre": nivel.Nivel, "unidades": unidades})

    periodos = [
        {
            "id": int(p.Id_Periodo),
            "periodo": p.Periodo,
            "activo": str(p.Periodo) == periodo_literal,
        }
        for p in db.query(CatPeriodo).order_by(CatPeriodo.Id_Periodo.desc()).all()
    ]

    return {
        "success": True,
        "periodo": periodo_literal,
        "periodos": periodos,
        "niveles": niveles,
    }


@router.get("/tabla", response_class=JSONResponse)
def tabla_validacion(
    id_periodo: int,
    id_nivel: int,
    sess=Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Tabla de validación: una fila por Unidad Académica del nivel elegido, con el estado
    de Matrícula / Aprovechamiento / Egresados / Titulados.

    - Matrícula (Formato 1): semáforo del periodo seleccionado.
    - Aprovechamiento, Egresados y Titulados (Formatos 2, 3 y 4): semáforo del periodo
      anterior (los SPs reciben el seleccionado y leen periodo - 1).
    - Un rol puede validar/rechazar solo cuando Id_Semaforo == Id_Rol - 1.
    """
    id_rol = _exigir_rol(sess)

    periodo = db.query(CatPeriodo).filter(CatPeriodo.Id_Periodo == id_periodo).first()
    nivel = db.query(Nivel).filter(Nivel.Id_Nivel == id_nivel).first()
    if not periodo or not nivel:
        raise HTTPException(status_code=404, detail="Periodo o Nivel no encontrado.")

    periodo_ant_id = id_periodo - 1
    roles_map = {int(r.Id_Rol): r.Rol for r in db.query(CatRoles).all()}
    semaforos_desc = {
        int(s.Id_Semaforo): s.Descripcion_Semaforo for s in db.query(CatSemaforo).all()
    }

    # Unidades que tienen registros en el nivel elegido
    unidades = (
        db.query(Unidad_Academica)
        .join(
            SemaforoUnidadAcademica,
            Unidad_Academica.Id_Unidad_Academica == SemaforoUnidadAcademica.Id_Unidad_Academica,
        )
        .filter(Unidad_Academica.Id_Estatus == 1, SemaforoUnidadAcademica.Id_Nivel == id_nivel)
        .distinct()
        .order_by(Unidad_Academica.Nombre)
        .all()
    )

    # Semáforos relevantes en una sola consulta
    filas_sem = (
        db.query(SemaforoUnidadAcademica)
        .filter(
            SemaforoUnidadAcademica.Id_Nivel == id_nivel,
            (
                (SemaforoUnidadAcademica.Id_Periodo == id_periodo)
                & (SemaforoUnidadAcademica.Id_Formato == 1)
            )
            | (
                (SemaforoUnidadAcademica.Id_Periodo == periodo_ant_id)
                & (SemaforoUnidadAcademica.Id_Formato.in_([2, 3, 4]))
            ),
        )
        .all()
    )
    semaforos: dict[tuple[int, int], list[int]] = {}
    for f in filas_sem:
        if f.Id_Semaforo is None:
            continue
        semaforos.setdefault(
            (int(f.Id_Unidad_Academica), int(f.Id_Formato)), []
        ).append(int(f.Id_Semaforo))

    filas = []
    for ua in unidades:
        modulos = {}
        for id_formato, clave, etiqueta in MODULOS:
            item = {
                "clave": clave,
                "nombre": etiqueta,
                "semaforo": None,
                "estado": "sin_datos",
                "descripcion": "Sin información",
                "puede_validar": False,
                "esperando_por": None,
            }
            valores = semaforos.get((int(ua.Id_Unidad_Academica), id_formato), [])
            if valores:
                # Si hay registros duplicados, se prioriza el que está en turno del rol
                semaforo = (id_rol - 1) if (id_rol - 1) in valores else valores[0]
                item["semaforo"] = semaforo
                item["descripcion"] = semaforos_desc.get(semaforo) or f"Estado {semaforo}"
                if semaforo == id_rol - 1:
                    item["estado"] = "pendiente"
                    item["puede_validar"] = True
                elif semaforo >= id_rol:
                    item["estado"] = "validado"
                else:
                    siguiente = semaforo + 1 if semaforo >= 3 else 3
                    item["estado"] = "espera"
                    item["esperando_por"] = roles_map.get(siguiente, "Rol previo")
            modulos[clave] = item
        filas.append({
            "unidad": {
                "id": int(ua.Id_Unidad_Academica),
                "sigla": ua.Sigla,
                "nombre": ua.Nombre,
            },
            "modulos": modulos,
        })

    return {
        "success": True,
        "periodo": periodo.Periodo,
        "id_rol": id_rol,
        "nivel": {"id": int(nivel.Id_Nivel), "nombre": nivel.Nivel},
        "filas": filas,
    }


@router.get("/modulos", response_class=JSONResponse)
def estado_modulos(
    id_unidad_academica: int,
    id_nivel: int,
    sess=Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Estado de Matrícula / Aprovechamiento / Egresados / Titulados para la UA + Nivel
    elegidos.

    Regla institucional (la misma que aplican los SPs):
    - Matrícula (Formato 1): evalúa el periodo activo.
    - Aprovechamiento, Egresados y Titulados (Formatos 2, 3 y 4): evalúan el periodo anterior
      (aunque los SPs reciban como parámetro el activo, leen periodo - 1).
    - Un rol puede validar/rechazar ÚNICAMENTE cuando Id_Semaforo == Id_Rol - 1.
    """
    id_rol = _exigir_rol(sess)
    periodo_id, periodo_literal = _periodo_activo(db)
    periodo_ant_id, periodo_ant_literal = get_periodo_anterior_al_ultimo(db)
    if not periodo_ant_id:
        periodo_ant_id = periodo_id - 1

    ua = db.query(Unidad_Academica).filter(
        Unidad_Academica.Id_Unidad_Academica == id_unidad_academica
    ).first()
    nivel = db.query(Nivel).filter(Nivel.Id_Nivel == id_nivel).first()
    if not ua or not nivel:
        raise HTTPException(status_code=404, detail="Unidad Académica o Nivel no encontrado.")

    roles_map = {int(r.Id_Rol): r.Rol for r in db.query(CatRoles).all()}
    semaforos_desc = {
        int(s.Id_Semaforo): s.Descripcion_Semaforo for s in db.query(CatSemaforo).all()
    }

    modulos = []
    for id_formato, clave, etiqueta in MODULOS:
        # Formato 1 usa periodo activo; Formatos 2, 3 y 4 usan periodo anterior
        target_periodo_id = periodo_id if id_formato == 1 else periodo_ant_id

        fila = (
            db.query(SemaforoUnidadAcademica)
            .filter(
                SemaforoUnidadAcademica.Id_Unidad_Academica == id_unidad_academica,
                SemaforoUnidadAcademica.Id_Periodo == target_periodo_id,
                SemaforoUnidadAcademica.Id_Formato == id_formato,
                SemaforoUnidadAcademica.Id_Nivel == id_nivel,
            )
            .first()
        )

        item = {
            "clave": clave,
            "nombre": etiqueta,
            "id_formato": id_formato,
            "semaforo": None,
            "estado": "sin_datos",
            "descripcion": "Sin información para este periodo",
            "puede_validar": False,
            "esperando_por": None,
        }

        if fila is not None and fila.Id_Semaforo is not None:
            semaforo = int(fila.Id_Semaforo)
            item["semaforo"] = semaforo
            item["descripcion"] = semaforos_desc.get(semaforo) or f"Estado {semaforo}"

            if semaforo == (id_rol - 1):
                item["estado"] = "pendiente"
                item["puede_validar"] = True
            elif semaforo >= id_rol:
                item["estado"] = "validado"
                item["puede_validar"] = False
            else:
                siguiente = semaforo + 1 if semaforo >= 3 else 3
                item["estado"] = "espera"
                item["esperando_por"] = roles_map.get(siguiente, "Rol previo")
                item["puede_validar"] = False

        modulos.append(item)

    return {
        "success": True,
        "periodo": periodo_literal,
        "unidad": {"id": int(ua.Id_Unidad_Academica), "sigla": ua.Sigla, "nombre": ua.Nombre},
        "nivel": {"id": int(nivel.Id_Nivel), "nombre": nivel.Nivel},
        "id_rol": id_rol,
        "modulos": modulos,
    }
