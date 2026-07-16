from backend.utils.email import EmailSendError, send_email
from typing import Dict, Union
from sqlalchemy.orm import Session
from backend.database.models.Usuario import Usuario
from backend.database.models.FormatoUsuario import Usuario as Formato_Usuario

def id_rol_a_nombre(id_rol: int) -> str:
    """
    Convierte un id_rol a su nombre correspondiente.
    NOTA: Ajusta los nombres según tu base de datos.
    """
    rol_map = {
        4: "CEGET",
        5: "Titular",
        6: "Analista",
        7: "Jefe de Departamento",
        8: "Jefe de División",
        9: "Director(a) de la DII"
    }
    return rol_map.get(id_rol, f"Rol desconocido (ID: {id_rol})")

def obtener_correos_involucrados(
    db: Session, 
    id_unidad: int, 
    id_formato: int
) -> Dict[str, str]:
    """
    Busca en la base de datos los correos del Capturista, CEGET y Titular
    basándose en la Unidad Académica y el Nivel.
    """
    ROLES_NOTIFICACION = {
        3: 'capturista', # 3 es Capturista
        4: 'ceget',      # 4 es CEGET
        5: 'titular'     # 5 es Titular
    }
    
    # Consultamos a los usuarios que pertenezcan a la UA, Nivel y tengan los roles que buscamos
    usuarios = db.query(Usuario).join(
        Formato_Usuario, Formato_Usuario.Id_Usuario == Usuario.Id_Usuario
    ).filter(
        Usuario.Id_Unidad_Academica == id_unidad,
        Formato_Usuario.Id_Formato == id_formato,
        Usuario.Id_Estatus == 1
    ).all()

    # Inicializamos el diccionario vacío
    correos = {
        'capturista': "",
        'ceget': "",
        'titular': ""
    }

    # Poblamos el diccionario con los correos encontrados
    for u in usuarios:
        if u.Email: # Verificamos que el usuario realmente tenga un correo registrado
            rol_clave = ROLES_NOTIFICACION.get(u.Id_Rol)
            if rol_clave:
                correos[rol_clave] = u.Email
                
    return correos

def notificar_rechazo_global(
    *,
    modulo_rechazado: str,
    id_rol_que_rechaza: int,
    correos: Dict[str, str]
) -> None:
    """
    Evalúa quién rechazó el módulo (por su id_rol) y envía un correo a los involucrados.
    'correos' debe ser: {'capturista': '...', 'ceget': '...', 'titular': '...'}
    """
    destinatarios = []

    # 1. Lógica inteligente de ruteo
    # NOTA: Ajusta el número 4 y 5 según el ID real de CEGET y Titular en tu base de datos
    if id_rol_que_rechaza == 4: # Suponiendo que 4 es CEGET
        if correos.get('capturista'): destinatarios.append(correos['capturista'])
        
    elif id_rol_que_rechaza == 5: # Suponiendo que 5 es Titular
        if correos.get('capturista'): destinatarios.append(correos['capturista'])
        if correos.get('ceget'): destinatarios.append(correos['ceget'])
        
    elif id_rol_que_rechaza in [6, 7, 8, 9]: # Roles superiores
        if correos.get('capturista'): destinatarios.append(correos['capturista'])
        if correos.get('ceget'): destinatarios.append(correos['ceget'])
        if correos.get('titular'): destinatarios.append(correos['titular'])
    else:
        print(f"Rol '{id_rol_que_rechaza}' no tiene configurado el envío de correos de rechazo.")
        return

    # Limpiar lista de nulos o vacíos
    destinatarios = [email for email in destinatarios if email]

    if not destinatarios:
        print("No hay destinatarios válidos para enviar el correo de rechazo.")
        return

    # 2. Plantilla HTML (adaptada a tu diseño del SiCAE)
    asunto = f"Aviso Importante: Rechazo en el módulo de {modulo_rechazado}"
    cuerpo = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
            <h2 style="color: #750946; text-align: center;">Notificación de Rechazo - SiCAE</h2>
            <p>Estimado usuario,</p>
            <p>Se le informa que el módulo <strong>{modulo_rechazado}</strong> ha sido rechazado para correcciones por el {id_rol_a_nombre(id_rol_que_rechaza)}.</p>
            
            <p style="color: #d9534f; font-weight: bold;">Por favor, ingrese al sistema para revisar las observaciones pertinentes.</p>
            <p style="margin-top: 20px;">Accede al sistema con el siguiente enlace:</p>
            <p style="text-align: center; margin: 30px 0;">
                <a href="http://148.204.107.39:50000" style="display: inline-block; padding: 12px 30px; background-color: #750946; color: white; text-decoration: none; border-radius: 5px; font-weight: bold;">Acceder a SiCAE</a>
            </p>
            <p style="margin-top: 30px; font-size: 12px; color: #777;">
                Este es un mensaje automático generado por SiCAE. Por favor, no responda a este correo.<br>
                <strong>Equipo SiCAE</strong>
            </p>
        </div>
    </body>
    </html>
    """

    # 3. Enviar el correo iterando sobre la lista de destinatarios
    if not destinatarios:
        print("No hay destinatarios válidos para enviar el correo de rechazo.")
        return
        
    for correo in destinatarios:
        try:
            send_email(correo, asunto, cuerpo)
            print(f"📧 Correo de rechazo enviado exitosamente a: {correo}")
        except Exception as e:
            print(f"❌ Error al enviar el correo de rechazo a {correo}: {str(e)}")


def html_correo_acuse( nombre_completo: str, periodo_activo: str,periodo_anterior: str, unidad_sigla: str, folio: str) -> str:
    """
    Genera el HTML para el correo de acuse de recibo.
    """
    return f"""
    <html>
    <body style="font-family: NotoSans, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
            <h2 style="color: #750946; text-align: center;">Acuse de Conclusión de Captura - SiCAE</h2>
            <p>A quien corresponda,</p>
            <p>Se le informa que concluyó la captura de información en el SiCAE conforme a lo siguiente:</p>
                    <ul>
                    <li><strong>Inicio:</strong> {periodo_activo} - <strong>Fin:</strong> {periodo_anterior}</li>
                    <li><strong>Unidad Academica:</strong> {unidad_sigla}</li>
                    <li><strong>Folio:</strong> {folio}</li>
                    </ul>
                        
            <p style="margin-top: 20px;">Por favor, guarde su acuse como comprobante de conclusión de captura.</p>
            <p style="margin-top: 30px; font-size: 12px; color: #777;">
                Este es un mensaje automático generado por SiCAE. Por favor, no responda a este correo.<br>
                <strong>SiCAE</strong>
            </p>
        </div>
    </body>
    </html>
    """