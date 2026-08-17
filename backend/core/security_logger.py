# backend/core/security_logger.py
"""
Módulo de Auditoría de Seguridad: Registro y Exportación de Incidentes.
-----------------------------------------------------------------------
Registra de forma persistente y thread-safe los incidentes de seguridad
(bloqueos por Rate Limiting, intentos de fuerza bruta y anomalías IDOR).

Los registros se almacenan en formato CSV con codificación UTF-8 con BOM (utf-8-sig),
lo que garantiza compatibilidad directa con Microsoft Excel y soporte para caracteres especiales.
"""

import os
import csv
import threading
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import Request

from backend.utils.request import get_request_host

# Directorio donde se guardarán los archivos CSV de auditoría
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOGS_DIR = os.path.join(BASE_DIR, "logs")

# Lock para asegurar escritura concurrente segura sin corrupción de archivos
_csv_lock = threading.Lock()

# Cabeceras estándar del archivo CSV
CSV_HEADERS = [
    "Fecha_Hora",
    "IP_Cliente",
    "Hostname",
    "Usuario_Objetivo",
    "Dispositivo_ID",
    "Endpoint",
    "Metodo",
    "Tipo_Incidente",
    "Accion_Tomada",
    "User_Agent"
]


def _ensure_logs_dir():
    """Crea la carpeta logs/ si no existe."""
    if not os.path.exists(LOGS_DIR):
        os.makedirs(LOGS_DIR, exist_ok=True)


def obtener_ruta_csv(mes_anio: Optional[str] = None) -> str:
    """
    Retorna la ruta absoluta del archivo CSV correspondiente al mes especificado.
    Formato esperado de mes_anio: 'YYYY-MM' (ej. '2026-08').
    Si no se especifica, utiliza el mes y año actual.
    """
    _ensure_logs_dir()
    if not mes_anio:
        mes_anio = datetime.now().strftime("%Y-%m")
    return os.path.join(LOGS_DIR, f"seguridad_bloqueos_{mes_anio}.csv")


def registrar_bloqueo_seguridad(
    request: Optional[Request],
    usuario_objetivo: str,
    tipo_incidente: str,
    accion_tomada: str,
    endpoint: Optional[str] = None,
    ip_forzada: Optional[str] = None,
    device_id: Optional[str] = None,
):
    """
    Registra un evento de bloqueo o anomalía en el archivo CSV de auditoría mensual.
    
    Parámetros:
    - request: Objeto Request de FastAPI (para extraer IP, User-Agent, endpoint, hostname y device_id).
    - usuario_objetivo: Nombre de usuario, correo o ID que fue objeto del intento.
    - tipo_incidente: Categoría del evento (ej. 'RATE_LIMIT_LOGIN', 'ANOMALIA_IDOR_UA').
    - accion_tomada: Respuesta del sistema (ej. 'BLOQUEO_HTTP_429 (60s)', 'BLOQUEO_TEMPORAL (300s)').
    - endpoint: Ruta URL opcional (si no se dispone de request o se desea sobreescribir).
    - ip_forzada: IP opcional si no proviene de un request directo.
    - device_id: Identificador único del dispositivo / navegador.
    """
    try:
        _ensure_logs_dir()
        fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Extracción de metadatos de la petición
        ip_cliente = ip_forzada or "unknown"
        user_agent = "Desconocido"
        metodo = "POST"
        ruta_endpoint = endpoint or "/desconocido"
        hostname = "unknown"
        dispositivo = device_id or "dev_unknown"

        if request:
            from backend.core.rate_limiter import get_client_ip, get_device_id
            ip_cliente = get_client_ip(request)
            user_agent = request.headers.get("user-agent", "Desconocido")
            metodo = request.method
            ruta_endpoint = endpoint or request.url.path
            dispositivo = device_id or get_device_id(request)
            try:
                hostname = get_request_host(request) or ip_cliente
            except Exception:
                hostname = ip_cliente

        fila = [
            fecha_hora,
            ip_cliente,
            hostname,
            str(usuario_objetivo or "No especificado"),
            str(dispositivo or "dev_unknown"),
            ruta_endpoint,
            metodo,
            tipo_incidente,
            accion_tomada,
            user_agent
        ]

        archivo_csv = obtener_ruta_csv()

        with _csv_lock:
            archivo_existe = os.path.exists(archivo_csv)
            with open(archivo_csv, mode="a", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                if not archivo_existe or os.path.getsize(archivo_csv) == 0:
                    writer.writerow(CSV_HEADERS)
                writer.writerow(fila)

        print(
            f"📝 [auditoria-seguridad] Incidente registrado en CSV: "
            f"Tipo={tipo_incidente} | IP={ip_cliente} | Dispositivo={dispositivo} | Usuario={usuario_objetivo} | Endpoint={ruta_endpoint}"
        )
    except Exception as e:
        print(f"❌ [auditoria-seguridad] Error al escribir en bitácora CSV: {e}")


def obtener_registros_seguridad(mes_anio: Optional[str] = None, limite: int = 500) -> List[Dict[str, Any]]:
    """
    Lee y devuelve los registros del archivo CSV ordenados del más reciente al más antiguo.
    """
    archivo_csv = obtener_ruta_csv(mes_anio)
    if not os.path.exists(archivo_csv):
        return []

    registros = []
    try:
        with _csv_lock:
            with open(archivo_csv, mode="r", newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    registros.append(dict(row))
        # Ordenar del más reciente al más antiguo
        registros.reverse()
        return registros[:limite]
    except Exception as e:
        print(f"❌ [auditoria-seguridad] Error al leer archivo CSV: {e}")
        return []


def obtener_metricas_seguridad(mes_anio: Optional[str] = None) -> Dict[str, Any]:
    """
    Calcula métricas clave para el panel de control del Administrador.
    """
    registros = obtener_registros_seguridad(mes_anio, limite=5000)
    
    total_incidentes = len(registros)
    accesos_no_autorizados_idor = sum(
        1 for r in registros 
        if "IDOR" in r.get("Tipo_Incidente", "").upper() or "NO_AUTORIZADO" in r.get("Tipo_Incidente", "").upper()
    )
    alertas_enumeracion_e3 = sum(
        1 for r in registros 
        if "ENUMERACION" in r.get("Tipo_Incidente", "").upper() or "BARRIDO" in r.get("Tipo_Incidente", "").upper() or "ANOMALIA" in r.get("Tipo_Incidente", "").upper()
    )
    bloqueos_rate_limit = sum(
        1 for r in registros 
        if "RATE_LIMIT" in r.get("Tipo_Incidente", "").upper()
    )
    reincidencias_penalizaciones = sum(
        1 for r in registros 
        if "REINCIDENCIA" in r.get("Tipo_Incidente", "").upper() or "PENALIZACION" in r.get("Tipo_Incidente", "").upper() or "TAMPERING" in r.get("Tipo_Incidente", "").upper()
    )
    ips_unicas = len(set(r.get("IP_Cliente") for r in registros if r.get("IP_Cliente")))
    dispositivos_unicos = len(set(r.get("Dispositivo_ID") for r in registros if r.get("Dispositivo_ID")))
    
    # Listar los meses disponibles que tengan archivos CSV en /logs
    meses_disponibles = []
    if os.path.exists(LOGS_DIR):
        for f in sorted(os.listdir(LOGS_DIR), reverse=True):
            if f.startswith("seguridad_bloqueos_") and f.endswith(".csv"):
                parte_fecha = f.replace("seguridad_bloqueos_", "").replace(".csv", "")
                meses_disponibles.append(parte_fecha)

    if not meses_disponibles:
        meses_disponibles.append(datetime.now().strftime("%Y-%m"))

    return {
        "total_incidentes": total_incidentes,
        "accesos_no_autorizados_idor": accesos_no_autorizados_idor,
        "alertas_enumeracion_e3": alertas_enumeracion_e3,
        "bloqueos_rate_limit": bloqueos_rate_limit,
        "reincidencias_penalizaciones": reincidencias_penalizaciones,
        "ips_unicas": ips_unicas,
        "dispositivos_unicos": dispositivos_unicos,
        "meses_disponibles": meses_disponibles,
        "mes_actual": mes_anio or datetime.now().strftime("%Y-%m")
    }
