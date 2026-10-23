import os
import base64
try:
    import msal
except ImportError:
    msal = None
import requests
from typing import Optional, TypedDict, Union, List
from backend.core.config import settings

class EmailSendError(Exception):
    pass


class EmailAttachment(TypedDict):
    filename: str
    content: bytes
    mime_type: str


def send_email(
    to_email: Union[str, List[str]],
    subject: str,
    html_body: str,
    from_email: Optional[str] = None,
    attachments: Optional[list[EmailAttachment]] = None,
):
    # 1. Definir remitente oficial (usando sicae@ipn.mx desde tus settings)
    if not from_email:
        from_email = getattr(settings, "SMTP_FROM", "sicae@ipn.mx")

    # Mantener tu lógica exacta de prefijos para mantener el estándar visual
    full_subject = f"{settings.SMTP_SUBJECT_PREFIX} - {subject}" if settings.SMTP_SUBJECT_PREFIX else subject

    # Normalizar destinatarios a lista sin vacíos ni duplicados
    if isinstance(to_email, str):
        destinatarios = [to_email]
    else:
        destinatarios = list(to_email)

    recipients_list = []
    seen = set()
    for email_addr in destinatarios:
        clean_addr = str(email_addr or "").strip()
        if clean_addr and clean_addr.lower() not in seen:
            seen.add(clean_addr.lower())
            recipients_list.append({"emailAddress": {"address": clean_addr}})

    if not recipients_list:
        raise EmailSendError("No se proporcionaron destinatarios válidos para enviar el correo.")

    try:
        # 2. Configurar autenticación con Microsoft Entra ID
        client_id = settings.MICROSOFT_CLIENT_ID or os.getenv("MICROSOFT_CLIENT_ID") or os.getenv("AZURE_CLIENT_ID") or ""
        tenant_id = settings.MICROSOFT_TENANT_ID or os.getenv("MICROSOFT_TENANT_ID") or os.getenv("AZURE_TENANT_ID") or ""
        client_secret = settings.MICROSOFT_CLIENT_SECRET or os.getenv("MICROSOFT_CLIENT_SECRET") or os.getenv("AZURE_CLIENT_SECRET") or ""
        
        if not tenant_id or not client_id or not client_secret:
            raise EmailSendError(
                "Faltan credenciales de Microsoft Graph en el archivo .env. "
                "Asegúrese de definir MICROSOFT_CLIENT_ID, MICROSOFT_TENANT_ID y MICROSOFT_CLIENT_SECRET en su archivo .env"
            )

        authority = f"https://login.microsoftonline.com/{tenant_id.strip('/')}"
        
        app = msal.ConfidentialClientApplication(
            client_id,
            authority=authority,
            client_credential=client_secret
        )

        # 3. Adquirir Token de Acceso para Microsoft Graph
        scopes = ["https://graph.microsoft.com/.default"]
        token_result = app.acquire_token_for_client(scopes=scopes)

        if "access_token" not in token_result:
            raise EmailSendError(
                f"Error de autenticación con Microsoft: {token_result.get('error_description')}"
            )

        access_token = token_result["access_token"]

        # 4. Construir la estructura del mensaje para Microsoft Graph
        # Separamos el html_body en la estructura JSON correspondiente
        message_json = {
            "subject": full_subject,
            "body": {
                "contentType": "HTML",
                "content": html_body
            },
            "toRecipients": recipients_list,
            "attachments": []
        }

        # 5. Procesar los archivos adjuntos (Ej. El PDF del acuse de matrícula)
        for attachment in attachments or []:
            filename = str(attachment.get('filename') or 'adjunto.bin')
            content_bytes = attachment.get('content') or b''
            mime_type = str(attachment.get('mime_type') or 'application/octet-stream')
            
            # Microsoft Graph exige que el contenido binario esté codificado en un string Base64
            base64_content = base64.b64encode(content_bytes).decode('utf-8')
            
            message_json["attachments"].append({
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": filename,
                "contentType": mime_type,
                "contentBytes": base64_content
            })

        # 6. Realizar la petición HTTP POST hacia el endpoint de Exchange Online
        url_api = f"https://graph.microsoft.com/v1.0/users/{from_email}/sendMail"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "message": message_json,
            "saveToSentItems": "true"  # Guarda copia en la bandeja de enviados de sicae@ipn.mx
        }

        response = requests.post(url_api, json=payload, headers=headers)

        # El código HTTP 202 Indica que Exchange aceptó y procesó el envío del correo con éxito
        if response.status_code != 202:
            raise EmailSendError(f"Código de error Graph: {response.status_code} - {response.text}")

    except Exception as e:
        # AGREGA ESTE PRINT TEMPORAL PARA VER EL ERROR EN CONSOLA:
        print(f"- DETALLE DEL ERROR REAL: {e}")
        raise EmailSendError(f"Error enviando correo por Microsoft Graph: {e}")