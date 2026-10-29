"""
Servicio para gestionar operaciones relacionadas con Periodos.
"""
from sqlalchemy.orm import Session
from typing import Optional, Tuple, List, Dict, Any
from backend.database.models.CatPeriodo import CatPeriodo


def get_ultimo_periodo(db: Session) -> Tuple[Optional[int], Optional[str]]:
    """
    Obtiene el último periodo creado en la base de datos.
    
    Args:
        db: Sesión de base de datos
        
    Returns:
        Tuple[Optional[int], Optional[str]]: (Id_Periodo, Periodo literal)
        Retorna (None, None) si no hay periodos en la base de datos
    
    Ejemplo:
        >>> id_periodo, periodo_literal = get_ultimo_periodo(db)
        >>> print(id_periodo, periodo_literal)
        7, '2025-2026/1'
    """
    try:
        # Obtener el último periodo ordenado por Id_Periodo descendente
        ultimo_periodo = db.query(CatPeriodo).order_by(
            CatPeriodo.Id_Periodo.desc()
        ).first()
        
        if ultimo_periodo:
            return ultimo_periodo.Id_Periodo, ultimo_periodo.Periodo
        
        # Si no hay periodos, retornar None
        return None, None
        
    except Exception as e:
        print(f"Error al obtener último periodo: {e}")
        return None, None


def get_periodo_activo(db: Session) -> Tuple[Optional[int], Optional[str]]:

    """
    Obtiene el periodo activo (Id_Estatus = 1).
    Si hay múltiples activos, retorna el más reciente.
    Si no hay activos, retorna el último periodo creado.
    
    Args:
        db: Sesión de base de datos
        
    Returns:
        Tuple[Optional[int], Optional[str]]: (Id_Periodo, Periodo literal)
    """
    try:
        # Intentar obtener periodo activo
        periodo_activo = db.query(CatPeriodo).filter(
            CatPeriodo.Id_Estatus == 1
        ).order_by(
            CatPeriodo.Id_Periodo.desc()
        ).first()
        
        if periodo_activo:
            return periodo_activo.Id_Periodo, periodo_activo.Periodo
        
        # Si no hay periodo activo, usar el último creado
        return get_ultimo_periodo(db)
        
    except Exception as e:
        print(f"Error al obtener periodo activo: {e}")
        return None, None


def get_periodo_por_id(db: Session, id_periodo: int) -> Optional[str]:
    """
    Obtiene el periodo literal por su ID.
    
    Args:
        db: Sesión de base de datos
        id_periodo: ID del periodo a buscar
        
    Returns:
        Optional[str]: Periodo literal o None si no se encuentra
    """
    try:
        periodo = db.query(CatPeriodo).filter(
            CatPeriodo.Id_Periodo == id_periodo
        ).first()
        
        return periodo.Periodo if periodo else None
        
    except Exception as e:
        print(f"Error al obtener periodo por ID: {e}")
        return None

def get_periodo_anterior_al_ultimo(db: Session) -> Tuple[Optional[int], Optional[str]]:
    """
    Obtiene el penúltimo periodo creado en la base de datos (offset 1 del último).
    
    Args:
        db: Sesión de base de datos
        
    Returns:
        Tuple[Optional[int], Optional[str]]: (Id_Periodo, Periodo literal)
        Retorna (None, None) si hay menos de 2 periodos en la base de datos.
    """
    try:
        # Ordenamos descendente y saltamos el primero (el último) para tomar el siguiente
        periodo_anterior = db.query(CatPeriodo).order_by(
            CatPeriodo.Id_Periodo.desc()
        ).offset(1).first()
        
        if periodo_anterior:
            return periodo_anterior.Id_Periodo, periodo_anterior.Periodo
        
        # Si no existe un penúltimo (solo hay 0 o 1 registros), retornar None
        return None, None
        
    except Exception as e:
        print(f"Error al obtener el periodo anterior al último: {e}")
        return None, None
    
def get_todos_los_periodos(db: Session) -> List[Dict[str, Any]]:
    """
    Obtiene la lista completa de periodos indicando su estado de activación.
    
    Args:
        db: Sesión de base de datos
        
    Returns:
        List[Dict[str, Any]]: Lista de diccionarios con la estructura:
        [{'id': 1, 'periodo': '2024-2025/1', 'esta_activo': True}, ...]
    """
    try:
        # Consultamos todos los periodos ordenados del más reciente al más antiguo
        periodos = db.query(CatPeriodo).order_by(CatPeriodo.Id_Periodo.desc()).all()
        
        return [
            {
                "Id_Periodo": p.Id_Periodo,
                "Periodo": p.Periodo,
                "Id_Estatus": p.Id_Estatus
            }
            for p in periodos
        ]
        
    except Exception as e:
        print(f"Error al listar todos los periodos: {e}")
        return []


from sqlalchemy import text


def get_periodo_abierto(db: Session) -> Tuple[Optional[int], Optional[str]]:
    """
    Obtiene únicamente el periodo actualmente abierto/activo (Id_Estatus == 1),
    sin hacer fallback al último periodo cerrado.
    """
    try:
        periodo_activo = db.query(CatPeriodo).filter(
            CatPeriodo.Id_Estatus == 1
        ).order_by(
            CatPeriodo.Id_Periodo.desc()
        ).first()

        if periodo_activo:
            return int(periodo_activo.Id_Periodo), str(periodo_activo.Periodo)

        return None, None
    except Exception as e:
        print(f"Error al obtener periodo abierto: {e}")
        return None, None


def evaluar_semaforos_periodo(db: Session, periodo_literal: str) -> Dict[str, Any]:
    """
    Evalúa el estado de todos los semáforos (UAs, niveles y módulos/formatos)
    correspondientes al periodo indicado:
      - Formato 1 (Matrícula): Id_Periodo == per.Id_Periodo
      - Formatos != 1 (Aprovechamiento, Egresados, Titulados): Id_Periodo == per.Id_Periodo - 1

    Exige que TODOS los semáforos estén en 9 (validados por Director/a de DII).
    """
    resumen = {
        "periodo": periodo_literal,
        "total_registros": 0,
        "completados_9": 0,
        "pendientes_registros": 0,
        "unidades_faltantes": 0,
        "total_unidades": 0,
        "listo_para_cerrar": False,
    }
    if not periodo_literal:
        return resumen

    try:
        sql = text("""
            SELECT
                COUNT(*) AS total_registros,
                SUM(CASE WHEN sem.Id_Semaforo >= 9 THEN 1 ELSE 0 END) AS completados_9,
                SUM(CASE WHEN sem.Id_Semaforo < 9 THEN 1 ELSE 0 END) AS pendientes_registros,
                COUNT(DISTINCT CASE WHEN sem.Id_Semaforo < 9 THEN sem.Id_Unidad_Academica END) AS unidades_faltantes,
                COUNT(DISTINCT sem.Id_Unidad_Academica) AS total_unidades
            FROM dbo.Semaforo_Unidad_Academica sem
            INNER JOIN dbo.Cat_Periodo per
                ON per.Periodo = :PPeriodo
                AND (
                    (sem.Id_Periodo = per.Id_Periodo AND sem.Id_Formato = 1)
                    OR
                    (sem.Id_Periodo = per.Id_Periodo - 1 AND sem.Id_Formato != 1)
                )
        """)
        row = db.execute(sql, {"PPeriodo": periodo_literal}).mappings().first()
        if row:
            total = int(row.get("total_registros") or 0)
            comp = int(row.get("completados_9") or 0)
            pend = int(row.get("pendientes_registros") or 0)
            ua_falt = int(row.get("unidades_faltantes") or 0)
            ua_tot = int(row.get("total_unidades") or 0)

            resumen.update({
                "total_registros": total,
                "completados_9": comp,
                "pendientes_registros": pend,
                "unidades_faltantes": ua_falt,
                "total_unidades": ua_tot,
                "listo_para_cerrar": (total > 0 and pend == 0),
            })
    except Exception as e:
        print(f"Error al evaluar semáforos del periodo {periodo_literal}: {e}")

    return resumen


def cerrar_periodo_activo(
    db: Session,
    usuario: str,
    host: str,
    periodo_literal: Optional[str] = None,
    auto: bool = False,
) -> Dict[str, Any]:
    """
    Cierra el periodo activo ejecutando [dbo].[SP_Cierra_Periodo] únicamente
    cuando TODOS los semáforos de las Unidades Académicas (todos los niveles
    y módulos) se encuentran en 9.
    """
    try:
        id_abierto, literal_abierto = get_periodo_abierto(db)
        if not literal_abierto:
            return {
                "success": False,
                "closed": False,
                "auto": auto,
                "message": "No hay un periodo activo abierto para cerrar.",
            }

        target_periodo = (periodo_literal or literal_abierto).strip()
        if target_periodo != literal_abierto:
            # Verificar si el periodo solicitado existe y ya está cerrado
            per_obj = db.query(CatPeriodo).filter(CatPeriodo.Periodo == target_periodo).first()
            if not per_obj:
                return {
                    "success": False,
                    "closed": False,
                    "auto": auto,
                    "message": f"El periodo {target_periodo} no existe.",
                }
            if int(per_obj.Id_Estatus or 0) != 1:
                return {
                    "success": False,
                    "closed": False,
                    "auto": auto,
                    "message": f"El periodo {target_periodo} ya se encuentra cerrado.",
                }

        resumen = evaluar_semaforos_periodo(db, target_periodo)

        if resumen["total_registros"] == 0:
            return {
                "success": False,
                "closed": False,
                "auto": auto,
                "periodo": target_periodo,
                "resumen": resumen,
                "message": f"El periodo {target_periodo} no cuenta con semáforos configurados.",
            }

        # Validar que TODOS los semáforos estén en 9
        if not resumen["listo_para_cerrar"]:
            ua_faltantes = resumen["unidades_faltantes"]
            mod_faltantes = resumen["pendientes_registros"]
            mensaje_rechazo = (
                f"El periodo {target_periodo} no se puede cerrar, faltan "
                f"{ua_faltantes} Unidades Academicas"
            )
            if not auto:
                try:
                    db.execute(
                        text("""
                            EXEC [dbo].[SP_Registra_Bitacora]
                                @Usuario = :Usuario,
                                @Modulo = 'Mod_Matricula',
                                @Periodo = :Periodo,
                                @Accion = :Accion,
                                @Host = :Host
                        """),
                        {
                            "Usuario": usuario or "sistema",
                            "Periodo": target_periodo,
                            "Accion": mensaje_rechazo[:250],
                            "Host": host or "127.0.0.1",
                        },
                    )
                    db.commit()
                except Exception as e_bit:
                    db.rollback()
                    print(f"Aviso al registrar bitácora de intento de cierre: {e_bit}")

            return {
                "success": False,
                "closed": False,
                "auto": auto,
                "periodo": target_periodo,
                "resumen": resumen,
                "message": (
                    f"{mensaje_rechazo} ({mod_faltantes} semáforo(s) aún no están en '9')."
                ),
            }

        # Todos los semáforos están en 9 -> Ejecutar SP_Cierra_Periodo
        result = db.execute(
            text("""
                SET NOCOUNT ON;
                EXEC [dbo].[SP_Cierra_Periodo]
                    @PPeriodo = :PPeriodo,
                    @UUsuario = :UUsuario,
                    @HHost = :HHost
            """),
            {
                "PPeriodo": target_periodo,
                "UUsuario": usuario or "sistema",
                "HHost": host or "127.0.0.1",
            },
        )

        sp_msg = None
        try:
            rows = result.fetchall()
            if rows and len(rows) > 0 and len(rows[0]) > 0:
                sp_msg = str(rows[0][0])
        except Exception:
            sp_msg = None

        db.commit()

        if sp_msg and "no se puede cerrar" in sp_msg.lower():
            return {
                "success": False,
                "closed": False,
                "auto": auto,
                "periodo": target_periodo,
                "resumen": resumen,
                "message": sp_msg,
            }

        return {
            "success": True,
            "closed": True,
            "auto": auto,
            "periodo": target_periodo,
            "resumen": resumen,
            "message": f"Se cerró exitosamente el periodo {target_periodo}.",
        }

    except Exception as e:
        db.rollback()
        print(f"Error al cerrar el periodo activo: {e}")
        return {
            "success": False,
            "closed": False,
            "auto": auto,
            "message": f"Error al intentar cerrar el periodo: {str(e)}",
        }


def verificar_y_cerrar_periodo_automatico(
    db: Session,
    usuario: str,
    host: str,
    periodo_literal: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Monitorea si todos los semáforos del periodo activo ya llegaron a '9'.
    Si todos están en '9', cierra automáticamente el periodo ejecutando SP_Cierra_Periodo.
    """
    try:
        _, literal_abierto = get_periodo_abierto(db)
        if not literal_abierto:
            return {"closed": False, "auto": True}

        target = literal_abierto
        resumen = evaluar_semaforos_periodo(db, target)
        if resumen.get("listo_para_cerrar"):
            print(f"🔒 Todos los semáforos del periodo {target} están en 9. Cerrando periodo automáticamente...")
            return cerrar_periodo_activo(
                db=db,
                usuario=usuario,
                host=host,
                periodo_literal=target,
                auto=True,
            )
        return {"closed": False, "auto": True, "resumen": resumen}
    except Exception as e:
        print(f"Error en monitoreo automático de cierre de periodo: {e}")
        return {"closed": False, "auto": True, "error": str(e)}
