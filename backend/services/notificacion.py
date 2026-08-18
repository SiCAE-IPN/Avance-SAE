from sqlalchemy.orm import Session
from backend.database.models.Validacion import Validacion
from backend.database.models.Usuario import Usuario
from backend.database.models.SemaforoUnidadAcademica import SemaforoUnidadAcademica

def notificacion_rechazo(
        db: Session,
        periodo_anterior_id: int,
        Id_Unidad_Academica: int,       
        id_formato: int,
        id_nivel: int = None): 

    # 1. Si el semáforo institucional está totalmente validado (Id_Semaforo >= 9), no hay rechazo
    query_semaforo = db.query(SemaforoUnidadAcademica).filter(
        SemaforoUnidadAcademica.Id_Periodo == periodo_anterior_id,
        SemaforoUnidadAcademica.Id_Unidad_Academica == Id_Unidad_Academica,
        SemaforoUnidadAcademica.Id_Formato == id_formato
    )
    if id_nivel:
        query_semaforo = query_semaforo.filter(SemaforoUnidadAcademica.Id_Nivel == id_nivel)
    
    semaforo_ua = query_semaforo.first()
    if semaforo_ua and semaforo_ua.Id_Semaforo >= 9:
        try:
            print(f"[Notificacion] UA {Id_Unidad_Academica} (Formato {id_formato}) totalmente validada (Semáforo {semaforo_ua.Id_Semaforo}).")
        except Exception:
            pass
        return {}

    # 2. Obtener el ÚLTIMO movimiento de Validación/Rechazo para la UA, Periodo y Formato
    query_ultimo = (
        db.query(Validacion)
        .filter(
            Validacion.Id_Periodo == periodo_anterior_id,
            Validacion.Id_Formato == id_formato,
            Validacion.Id_Unidad_Academica == Id_Unidad_Academica
        )
    )
    if id_nivel:
        query_ultimo = query_ultimo.filter(Validacion.Id_Nivel == id_nivel)

    ultimo_movimiento_ua = query_ultimo.order_by(Validacion.Fecha.desc()).first()

    # Si no hay movimientos o el último movimiento fue una VALIDACIÓN (Validado == 1 o Validado != 0), NO hay rechazo vigente
    if not ultimo_movimiento_ua or int(ultimo_movimiento_ua.Validado or 0) != 0:
        return {}

    # Si el último movimiento es efectivamente un RECHAZO (Validado == 0):
    usuario = db.query(Usuario).filter(Usuario.Id_Usuario == ultimo_movimiento_ua.Id_Usuario).first()
    rechazado_por = f"{usuario.Nombre} {usuario.Paterno} {usuario.Materno}".strip() if usuario else "Validador"
    mensaje_rechazo = ultimo_movimiento_ua.Nota or "Sin especificar motivo"
    fecha = ultimo_movimiento_ua.Fecha

    try:
        print(f"[Notificacion] Rechazo vigente detectado en UA {Id_Unidad_Academica}: {mensaje_rechazo} por {rechazado_por} ({fecha})")
    except Exception:
        pass

    return {
        "fecha": fecha.strftime("%d/%m/%Y %H:%M") if fecha else "",
        "motivo": mensaje_rechazo,
        "rechazado_por": rechazado_por
    }