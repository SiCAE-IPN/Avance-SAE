from backend.utils.email import EmailSendError, send_email
from typing import Dict, Optional, Tuple, Union
from datetime import datetime
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

    # 3. Enviar un único correo con todos los destinatarios juntos
    # Limpiar y deduplicar destinatarios
    destinatarios_unicos = []
    seen = set()
    for email in destinatarios:
        clean = (email or "").strip()
        if clean and clean.lower() not in seen:
            seen.add(clean.lower())
            destinatarios_unicos.append(clean)

    if not destinatarios_unicos:
        print("No hay destinatarios válidos para enviar el correo de rechazo.")
        return

    try:
        send_email(to_email=destinatarios_unicos, subject=asunto, html_body=cuerpo)
        print(f"📧 Correo de rechazo enviado exitosamente a: {', '.join(destinatarios_unicos)}")
    except Exception as e:
        print(f"❌ Error al enviar el correo de rechazo a {destinatarios_unicos}: {str(e)}")


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


def enviar_correo_acuse_titular(
    *,
    db: Session,
    id_usuario: int,
    usuario_login: str,
    nombre_completo: str,
    unidad_sigla: str,
    unidad_nombre: str,
    clave_ur: Optional[str],
    periodo_literal: str,
    estatus_entrega: str = "",
) -> Tuple[Optional[dict], bool, Optional[str], Optional[str]]:
    """
    Genera el PDF de acuse, lo guarda en disco y envía el correo al titular.

    Retorna:
        (acuse_info, correo_enviado, acuse_error, correo_error)
        - acuse_info: dict con folio/file_name/download_url, o None si falló
        - correo_enviado: True si el correo fue enviado exitosamente
        - acuse_error: mensaje de error al generar/guardar PDF, o None
        - correo_error: mensaje de error al enviar correo, o None
    """
    from backend.services.acuse_service import build_folio_acuse, save_acuse_pdf_for_user
    from backend.utils.acuse_pdf import generar_acuse_matricula_pdf_en_memoria
    from backend.services.periodo_service import get_periodo_anterior_al_ultimo
    from backend.database.models.CatPeriodo import CatPeriodo

    acuse_info = None
    correo_enviado = False
    acuse_error = None
    correo_error = None

    try:
        # Si no viene indicado como extemporaneo, verificar contra CatPeriodo.Fecha_Final_Periodo
        if not estatus_entrega or "extempor" not in str(estatus_entrega).lower():
            try:
                per_db = db.query(CatPeriodo).filter(CatPeriodo.Periodo == periodo_literal).first()
                if per_db and per_db.Fecha_Final_Periodo:
                    fecha_fin = per_db.Fecha_Final_Periodo
                    fecha_fin_date = fecha_fin.date() if hasattr(fecha_fin, "date") else fecha_fin
                    if fecha_fin_date < datetime.now().date():
                        estatus_entrega = "Extemporaneo"
            except Exception as _e_per:
                print(f"ℹ️ No se pudo evaluar Fecha_Final_Periodo: {_e_per}")

        folio_acuse = build_folio_acuse(
            periodo_literal=periodo_literal,
            unidad_sigla=unidad_sigla,
            estatus_entrega=estatus_entrega,
        )

        pdf_bytes = generar_acuse_matricula_pdf_en_memoria(
            escuela=unidad_nombre or unidad_sigla,
            sigla=unidad_sigla,
            folio=folio_acuse,
            clave_ur=clave_ur or None,
            fecha_evento=datetime.now(),
            estatus_entrega=estatus_entrega,
            db=db,
        )

        acuse_guardado = save_acuse_pdf_for_user(
            usuario_login=usuario_login,
            folio=folio_acuse,
            periodo_literal=periodo_literal,
            unidad_sigla=unidad_sigla,
            pdf_bytes=pdf_bytes,
        )
        acuse_info = {
            "folio": acuse_guardado.folio,
            "file_name": acuse_guardado.file_name,
            "download_url": acuse_guardado.relative_url,
        }
        print(f"📄 Acuse PDF generado -> folio={folio_acuse}, archivo={acuse_guardado.file_name}")

        # Obtener periodo anterior para el cuerpo del correo
        _, periodo_anterior_literal = get_periodo_anterior_al_ultimo(db)
        periodo_anterior_literal = periodo_anterior_literal or "N/A"

        usuario_db = db.query(Usuario).filter(Usuario.Id_Usuario == id_usuario).first()
        correo_destino = str(usuario_db.Email or "").strip() if usuario_db else ""

        if correo_destino:
            try:
                send_email(
                    to_email=correo_destino,
                    subject="Conclusión de Captura de Información - SiCAE",
                    html_body=html_correo_acuse(
                        nombre_completo=nombre_completo,
                        periodo_activo=periodo_literal,
                        periodo_anterior=periodo_anterior_literal,
                        unidad_sigla=unidad_sigla,
                        folio=folio_acuse,
                    ),
                    attachments=[
                        {
                            "filename": acuse_guardado.file_name,
                            "content": pdf_bytes,
                            "mime_type": "application/pdf",
                        }
                    ],
                )
                correo_enviado = True
                print(f"📧 Acuse enviado por correo -> destino={correo_destino}, archivo={acuse_guardado.file_name}")
            except EmailSendError as e_mail:
                correo_error = str(e_mail)
                print(f"❌ Fallo envío de correo de acuse -> destino={correo_destino}, error={correo_error}")
        else:
            print(f"⚠️ No se envió correo de acuse: usuario sin email registrado. usuario={usuario_login}")

    except Exception as e_acuse:
        acuse_error = str(e_acuse)
        print(
            f"❌ Error al generar/guardar acuse PDF -> "
            f"periodo={periodo_literal}, unidad={unidad_sigla}, usuario={usuario_login}, error={acuse_error}"
        )

    return acuse_info, correo_enviado, acuse_error, correo_error


def verificar_todos_modulos_validados_titular(
    db: Session,
    id_unidad: int,
    id_nivel: Optional[int] = None,
) -> bool:
    """
    Verifica si los 4 formatos (Matrícula, Aprovechamiento, Egresados, Titulados)
    de la Unidad Académica ya tienen un semáforo >= 5 (Validado por el Titular).
    """
    from backend.services.periodo_service import get_periodo_activo, get_periodo_anterior_al_ultimo
    from backend.database.models.SemaforoUnidadAcademica import SemaforoUnidadAcademica

    try:
        id_periodo_activo, p_act = get_periodo_activo(db)
        id_periodo_anterior, p_ant = get_periodo_anterior_al_ultimo(db)

        # Mapa de formato -> periodo_id correspondiente
        # Formato 1 (Matrícula) usa Periodo Activo
        # Formatos 2 (Aprovechamiento), 3 (Egresados), 4 (Titulados) usan Periodo Anterior
        formatos_esperados = {
            1: (id_periodo_activo, p_act, "Matrícula"),
            2: (id_periodo_anterior, p_ant, "Aprovechamiento"),
            3: (id_periodo_anterior, p_ant, "Egresados"),
            4: (id_periodo_anterior, p_ant, "Titulados"),
        }

        print(f"\n🔍 [Verificación de Módulos para Acuse] UA ID: {id_unidad}")
        formatos_incompletos = []

        for id_fmt, (id_per, p_lit, fmt_nombre) in formatos_esperados.items():
            query = db.query(SemaforoUnidadAcademica).filter(
                SemaforoUnidadAcademica.Id_Unidad_Academica == id_unidad,
                SemaforoUnidadAcademica.Id_Periodo == id_per,
                SemaforoUnidadAcademica.Id_Formato == id_fmt,
            )
            if id_nivel and id_nivel > 0:
                row = query.filter(SemaforoUnidadAcademica.Id_Nivel == id_nivel).first() or query.first()
            else:
                row = query.first()

            sem_val = int(row.Id_Semaforo or 0) if row else 0
            print(f"   • {fmt_nombre} (Fmt {id_fmt}, P: {p_lit}): Semáforo = {sem_val}")

            # Se considera validado por Titular si el semáforo es >= 5
            if sem_val < 5:
                formatos_incompletos.append(fmt_nombre)

        if not formatos_incompletos:
            print("✅ TODOS los módulos de la UA están validados por el Titular (Semáforos >= 5). ¡Listo para enviar acuse!")
            return True
        else:
            print(f"⏳ Módulos pendientes de validación por Titular: {', '.join(formatos_incompletos)}")
            return False

    except Exception as e:
        print(f"❌ Error verificando semáforos de la UA: {e}")
        return False
