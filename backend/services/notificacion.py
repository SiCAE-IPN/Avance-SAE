from sqlalchemy.orm import Session
from backend.database.models.Validacion import Validacion
from backend.database.models.Usuario import Usuario

def notificacion_rechazo(
        db: Session,
        periodo_anterior_id: int,
        Id_Unidad_Academica: int,       
        id_formato: int): 

    mensaje_rechazo = None
    rechazado_por = None
    fecha = None

    ultimo_movimiento_ua = (
                db.query(Validacion)
                .join(Usuario, Usuario.Id_Usuario == Validacion.Id_Usuario)
                .filter(
                    Validacion.Id_Periodo == periodo_anterior_id,
                    Validacion.Id_Formato == id_formato,
                    Validacion.Validado == 0,
                    Usuario.Id_Unidad_Academica == Id_Unidad_Academica
                )
                .order_by(Validacion.Fecha.desc())
                .first()
            )
    rechazo_info = {}

    if ultimo_movimiento_ua:

        usuario = db.query(Usuario).filter(Usuario.Id_Usuario == ultimo_movimiento_ua.Id_Usuario ).first()

        mensaje_rechazo = ultimo_movimiento_ua.Nota

        rechazado_por = None
        
        rechazado_por = f"{usuario.Nombre} {usuario.Paterno} {usuario.Materno}".strip() if usuario else "Validador"
        
        print("Mensaje de rechazo: ", mensaje_rechazo)
        print("Rechazado por: ", rechazado_por)
        print("Fecha de rechazo: ", ultimo_movimiento_ua.Fecha)

        fecha = ultimo_movimiento_ua.Fecha

        rechazo_info = {
            "fecha" : fecha,
            "motivo": mensaje_rechazo,
            "rechazado_por" : rechazado_por
        }

    return rechazo_info