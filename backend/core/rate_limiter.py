# backend/core/rate_limiter.py
"""
Módulo de Seguridad: Rate Limiter y Detección de Anomalías con Aislamiento Criptográfico de Dispositivos (Anti-Tampering).
-------------------------------------------------------------------------------------------------------------------------
Este módulo provee mecanismos de protección contra:
1. Ataques de fuerza bruta (e.g., adivinar contraseñas en login o recuperación).
2. Enumeración y barrido horizontal de recursos (IDOR).
3. Sobrecarga por denegación de servicio (DoS) a nivel de aplicación.
4. Manipulación de cookies de cliente (Cookie Tampering en DevTools / EditThisCookie).

Aislamiento Criptográfico:
- La cookie `device_id` se firma digitalmente en el servidor usando HMAC-SHA256 vinculada a la IP y al User-Agent.
- Si un usuario edita, falsifica o inventa un `device_id` en su navegador, la firma digital falla,
  el servidor detecta la manipulación (Tampering), bloquea la petición inmediatamente con HTTP 403 y lo registra en el CSV.
"""

import os
import time
import hmac
import hashlib
from collections import defaultdict
from typing import Optional, Tuple
from fastapi import Request, HTTPException, status

# Clave secreta para la firma criptográfica HMAC de dispositivos
SECRET_KEY = os.getenv("SECRET_KEY", "SiCAE-Security-Device-Signing-Secret-Key-2026-v1")


def get_client_ip(request: Request) -> str:
    """
    Obtiene la dirección IP real del cliente considerando entornos de desarrollo
    y producción detrás de proxies inversos (Nginx, Traefik, IIS, Cloudflare).
    
    Orden de prioridad:
    1. Cabecera 'X-Forwarded-For' (toma la primera IP de la cadena).
    2. Cabecera 'X-Real-IP'.
    3. Dirección directa del socket del cliente (request.client.host).
    """
    if not request:
        return "unknown"

    # 1. Cabecera X-Forwarded-For (formato común: 'client, proxy1, proxy2')
    xff = request.headers.get("x-forwarded-for")
    if xff:
        ip = xff.split(",")[0].strip()
        if ip:
            return ip

    # 2. Cabecera X-Real-IP
    x_real_ip = request.headers.get("x-real-ip")
    if x_real_ip:
        ip = x_real_ip.strip()
        if ip:
            return ip

    # 3. IP directa de la conexión
    if request.client and request.client.host:
        return request.client.host

    return "unknown"


def _generar_firma_hmac(raw_device_id: str, ip: str, user_agent: str) -> str:
    """
    Genera una firma criptográfica HMAC-SHA256 ligando el ID del dispositivo
    a la IP pública del cliente y su navegador.
    """
    ua_normalizado = (user_agent or "").strip()[:80]
    payload = f"{raw_device_id}:{ip}:{ua_normalizado}"
    return hmac.new(SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()[:24]


def firmar_device_id(raw_device_id: str, request: Request) -> str:
    """
    Genera el valor firmado para guardar en la cookie del navegador:
    Formato: `<raw_device_id>.<firma_hmac_24chars>`
    """
    ip = get_client_ip(request)
    ua = request.headers.get("user-agent", "") if hasattr(request, "headers") else ""
    firma = _generar_firma_hmac(raw_device_id, ip, ua)
    return f"{raw_device_id}.{firma}"


def verificar_y_extraer_device_id(cookie_val: str, request: Request) -> Tuple[Optional[str], bool]:
    """
    Verifica la autenticidad de la firma digital de la cookie `device_id`.
    Retorna una tupla: `(raw_device_id, fue_manipulado)`
    
    - Si la firma coincide: `(raw_device_id, False)`
    - Si la firma fue alterada o no es válida: `(None, True)`
    """
    if not cookie_val or "." not in cookie_val:
        return None, True

    partes = cookie_val.split(".", 1)
    if len(partes) != 2:
        return None, True

    raw_id, firma_recibida = partes
    ip = get_client_ip(request)
    ua = request.headers.get("user-agent", "") if hasattr(request, "headers") else ""
    firma_esperada = _generar_firma_hmac(raw_id, ip, ua)

    # Comparación en tiempo constante para mitigar ataques de temporización (timing attacks)
    if hmac.compare_digest(firma_recibida, firma_esperada):
        return raw_id, False

    return None, True


def get_device_id_con_validacion(request: Request) -> Tuple[str, bool]:
    """
    Obtiene el identificador de dispositivo y valida si hubo manipulación de cookies (Tampering).
    
    Retorna:
    - (device_id, fue_manipulado: bool)
    """
    if not request:
        return "dev_unknown", False

    # 1. Verificar si viene la cookie 'device_id' en la petición
    if hasattr(request, "cookies"):
        dev_cookie = request.cookies.get("device_id")
        if dev_cookie and str(dev_cookie).strip() and not str(dev_cookie).startswith("<MagicMock"):
            raw_id, fue_manipulado = verificar_y_extraer_device_id(str(dev_cookie).strip(), request)
            if fue_manipulado:
                return "dev_tampered", True
            if raw_id:
                return raw_id, False

    # 2. Si fue inyectada previamente en request.state por middleware
    if hasattr(request, "state"):
        dev_state = getattr(request.state, "device_id", None)
        if dev_state and str(dev_state).strip() and not str(dev_state).startswith("<MagicMock"):
            return str(dev_state).strip(), False

    # 3. Fallback determinista si el navegador no tiene cookies (Modo Incógnito / Cookie borrada)
    client_ip = get_client_ip(request)
    ua = request.headers.get("user-agent", "") if hasattr(request, "headers") else ""
    h = hashlib.md5(f"{client_ip}_{ua}".encode("utf-8")).hexdigest()[:10]
    return f"dev_fb_{h}", False


def get_device_id(request: Request) -> str:
    """Función de compatibilidad que retorna el string del device_id."""
    dev_id, _ = get_device_id_con_validacion(request)
    return dev_id


async def _extraer_usuario_objetivo(request: Request) -> str:
    """
    Intenta extraer de forma segura y no destructiva el usuario o correo
    al que se intentó acceder en la petición HTTP.
    """
    if not request:
        return "No especificado"

    try:
        # 1. Intentar desde datos de Formulario primero (ideal para login / recuperación / registro)
        content_type = (request.headers.get("content-type") or "").lower()
        if "form" in content_type:
            form = await request.form()
            for campo in ["usuario_email", "email", "username", "usuario", "User", "Correo"]:
                if campo in form and form[campo]:
                    val = str(form[campo]).strip()
                    if val and not val.startswith("<MagicMock"):
                        return val

        # 2. Intentar desde sesión activa en request.state si existe
        if hasattr(request, "state"):
            sess = getattr(request.state, "session", None)
            if sess and hasattr(sess, "usuario"):
                u = getattr(sess, "usuario", None) or getattr(sess, "nombre_usuario", None)
                if u and not str(u).startswith("<MagicMock"):
                    return str(u)

        # 3. Intentar desde JSON body si ya fue parseado
        if hasattr(request, "_json") and request._json:
            j = request._json
            for campo in ["usuario_email", "email", "username", "usuario", "User", "Email", "Usuario"]:
                if campo in j and j[campo]:
                    return str(j[campo]).strip()

        # 4. Intentar desde Query Params
        for campo in ["usuario", "email", "user"]:
            if campo in request.query_params:
                return str(request.query_params[campo]).strip()

    except Exception:
        pass

    return "No identificado / Anónimo"


class InMemoryRateLimiter:
    """
    Rate Limiter en memoria basado en Ventana Deslizante (Sliding Window)
    con Aislamiento Criptográfico y Detección de Cookie Tampering.
    
    Parámetros:
    - requests_limit: Número máximo de peticiones permitidas dentro del intervalo.
    - window_seconds: Duración de la ventana de tiempo en segundos (ej. 60s = 1 minuto).
    - name: Nombre identificador para trazabilidad y logs de auditoría.
    """

    def __init__(self, requests_limit: int = 10, window_seconds: int = 60, name: str = "Default"):
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        self.name = name
        self.history = defaultdict(list)
        self.lockouts = {}  # {clave_rastreo: {"blocked_until": float, "lock_duration": int, "attempts_during_lock": int}}
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # Purgar registros inactivos cada 5 minutos

    def _cleanup_stale_records(self, now: float):
        """
        Mantenimiento de memoria: Elimina entradas que no tienen actividad reciente
        para evitar fugas de memoria (memory leak) a largo plazo.
        """
        if now - self._last_cleanup < self._cleanup_interval:
            return

        self._last_cleanup = now
        stale_keys = []
        for key, timestamps in list(self.history.items()):
            valid_timestamps = [t for t in timestamps if now - t < self.window_seconds]
            if not valid_timestamps and key not in self.lockouts:
                stale_keys.append(key)
            else:
                self.history[key] = valid_timestamps

        for key in stale_keys:
            self.history.pop(key, None)

        # Limpiar lockouts expirados
        expired_lockouts = [k for k, v in self.lockouts.items() if now >= v.get("blocked_until", 0)]
        for k in expired_lockouts:
            self.lockouts.pop(k, None)

    async def __call__(self, request: Request):
        """
        Método callable para integrarse como dependencia de FastAPI: `Depends(limiter_...)`
        """
        client_ip = get_client_ip(request)
        device_id, fue_manipulado = get_device_id_con_validacion(request)
        now = time.time()

        # Extraer usuario_objetivo
        usuario_objetivo = await _extraer_usuario_objetivo(request)

        # ----------------------------------------------------------------------
        # DETECCIÓN DE COOKIE TAMPERING (Manipulación de identificador de dispositivo)
        # ----------------------------------------------------------------------
        if fue_manipulado:
            print(
                f"🚨 [seguridad-tampering] MANIPULACIÓN DETECTADA: "
                f"IP={client_ip} | Endpoint={request.url.path} | Intento de alteración de device_id."
            )
            # Registrar en la bitácora de auditoría CSV
            from backend.core.security_logger import registrar_bloqueo_seguridad
            registrar_bloqueo_seguridad(
                request=request,
                usuario_objetivo=usuario_objetivo,
                tipo_incidente="COOKIE_TAMPERING_DEVICE_ID",
                accion_tomada="ACCESO_DENEGADO_HTTP_403",
                device_id="TAMPERED_INVALID_SIG"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Violación de integridad de seguridad: El identificador de dispositivo ha sido alterado o es inválido."
            )

        # Ejecutar mantenimiento periódico si corresponde
        self._cleanup_stale_records(now)

        # Determinar clave de rastreo compuesta para aislar por dispositivo y cuenta
        if self.name.lower() in ["login", "recuperación", "recuperacion"]:
            usuario_clean = usuario_objetivo.lower().strip()
            clave_rastreo = f"{device_id}_{usuario_clean}"
        else:
            clave_rastreo = f"{device_id}_{client_ip}"

        # ----------------------------------------------------------------------
        # 1. VERIFICAR SI YA TIENE UN BLOQUEO ACTIVO Y DUPLICAR POR INSISTENCIA
        # ----------------------------------------------------------------------
        if clave_rastreo in self.lockouts:
            lock_info = self.lockouts[clave_rastreo]
            blocked_until = lock_info.get("blocked_until", 0)

            if now < blocked_until:
                # El usuario/dispositivo sigue bloqueado e insiste en mandar solicitudes
                duracion_previa = lock_info.get("lock_duration", self.window_seconds)
                tiempo_restante = int(blocked_until - now)
                # Duplica el tiempo (mínimo el doble de la duración previa o tiempo restante * 2)
                nueva_duracion = min(3600, max(tiempo_restante * 2, duracion_previa * 2, 60))
                lock_info["blocked_until"] = now + nueva_duracion
                lock_info["lock_duration"] = nueva_duracion
                lock_info["attempts_during_lock"] = lock_info.get("attempts_during_lock", 0) + 1
                retry_after = nueva_duracion

                print(
                    f"🚨 [seguridad-rate-limit] REINCIDENCIA/INSISTENCIA ({self.name}): "
                    f"Dispositivo={device_id} | IP={client_ip} | Usuario={usuario_objetivo} | "
                    f"Intento #{lock_info['attempts_during_lock']} durante bloqueo. "
                    f"Tiempo duplicado a {retry_after}s."
                )

                # Registrar la penalización duplicada en CSV
                from backend.core.security_logger import registrar_bloqueo_seguridad
                registrar_bloqueo_seguridad(
                    request=request,
                    usuario_objetivo=usuario_objetivo,
                    tipo_incidente=f"REINCIDENCIA_BLOQUEO_{self.name.upper().replace(' ', '_')}",
                    accion_tomada=f"PENALIZACION_DUPLICADA_429 ({retry_after}s)",
                    device_id=device_id,
                )

                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        f"Demasiadas solicitudes ({self.name}). Has realizado intentos adicionales durante el bloqueo activo. "
                        f"Por seguridad, el tiempo de espera se ha duplicado a {retry_after} segundos."
                    ),
                    headers={"Retry-After": str(retry_after)},
                )
            else:
                # El bloqueo ya expiró, limpiar
                self.lockouts.pop(clave_rastreo, None)

        # ----------------------------------------------------------------------
        # 2. EVALUAR VENTANA DESLIZANTE DE PETICIONES
        # ----------------------------------------------------------------------
        timestamps = self.history[clave_rastreo]
        valid_timestamps = [t for t in timestamps if now - t < self.window_seconds]
        self.history[clave_rastreo] = valid_timestamps

        # Verificar si superó el límite de peticiones permitidas
        if len(valid_timestamps) >= self.requests_limit:
            oldest_ts = valid_timestamps[0]
            retry_after = max(1, int(self.window_seconds - (now - oldest_ts)))

            # Establecer bloqueo activo
            self.lockouts[clave_rastreo] = {
                "blocked_until": now + retry_after,
                "lock_duration": retry_after,
                "attempts_during_lock": 0
            }

            print(
                f"🚨 [seguridad-rate-limit] Límite alcanzado ({self.name}): "
                f"Dispositivo={device_id} | IP={client_ip} | Usuario={usuario_objetivo} | "
                f"Endpoint={request.url.path} | Peticiones={len(valid_timestamps)}/{self.requests_limit} en {self.window_seconds}s | "
                f"Retry-After={retry_after}s"
            )

            # Registrar en el archivo CSV de Auditoría de Seguridad
            from backend.core.security_logger import registrar_bloqueo_seguridad
            registrar_bloqueo_seguridad(
                request=request,
                usuario_objetivo=usuario_objetivo,
                tipo_incidente=f"RATE_LIMIT_{self.name.upper().replace(' ', '_')}",
                accion_tomada=f"BLOQUEO_HTTP_429 ({retry_after}s)",
                device_id=device_id,
            )

            # Lanza HTTP 429 con cabecera estándar de reintento
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Demasiadas solicitudes ({self.name}). Límite de {self.requests_limit} peticiones "
                    f"alcanzado para este dispositivo o cuenta. Por favor espere {retry_after} segundo(s) antes de intentar nuevamente."
                ),
                headers={"Retry-After": str(retry_after)},
            )

        # Registrar la marca de tiempo de la petición actual
        self.history[clave_rastreo].append(now)


# ==============================================================================
# INSTANCIAS PRECONFIGURADAS PARA DISTINTOS NIVELES DE SENSIBILIDAD
# ==============================================================================

# 1. Login: 2 intentos por minuto por dispositivo/cuenta
limiter_login = InMemoryRateLimiter(
    requests_limit=2,
    window_seconds=60,
    name="Login",
)

# 2. Recuperación: 5 intentos por minuto por dispositivo/cuenta
limiter_recuperacion = InMemoryRateLimiter(
    requests_limit=5,
    window_seconds=60,
    name="Recuperación",
)

# 3. Operaciones Sensibles: 30 peticiones por minuto por dispositivo (Creación/edición/baja)
limiter_sensible = InMemoryRateLimiter(
    requests_limit=30,
    window_seconds=60,
    name="Operaciones Sensibles",
)

# 4. Operaciones Críticas / Estrictas: 5 peticiones por minuto por dispositivo
limiter_estricto = InMemoryRateLimiter(
    requests_limit=5,
    window_seconds=60,
    name="Operaciones Críticas",
)


# ==============================================================================
# DETECTOR DE PATRONES ANÓMALOS (BARRIDO HORIZONTAL / IDOR / ENUMERACIÓN E3)
# ==============================================================================

class AnomalyDetector:
    """
    Detector de anomalías y comportamiento malicioso (Cumplimiento Cuestionario E3).
    Monitorea si un usuario o dispositivo intenta acceder consecutivamente a recursos no autorizados (IDOR).
    
    Parámetros:
    - threshold_distinct_resources: Cantidad de recursos distintos no autorizados antes de alertar (3).
    - window_seconds: Intervalo de tiempo para acumular las alertas (60s).
    - block_duration_seconds: Duración del bloqueo temporal si se excede el umbral (300s = 5 min).
    """

    def __init__(
        self,
        threshold_distinct_resources: int = 3,
        window_seconds: int = 60,
        block_duration_seconds: int = 300,
    ):
        self.threshold = threshold_distinct_resources
        self.window_seconds = window_seconds
        self.block_duration_seconds = block_duration_seconds
        self.attempts = defaultdict(list)
        self.blocked_until = {}  # {user_id_or_device: timestamp_fin_bloqueo}
        self.block_durations = {}  # {user_id_or_device: duracion_actual}
        self.attempts_during_lock = defaultdict(int)

    def registrar_intento_no_autorizado(
        self, user_id_or_ip: str, resource_id: str, endpoint: str, device_id: Optional[str] = None
    ) -> bool:
        """
        Registra un intento de acceso a un recurso ajeno o no autorizado.
        Retorna True si se detectó un patrón de barrido anómalo y se activó la alerta/bloqueo E3.
        """
        now = time.time()
        identificador = str(user_id_or_ip or "unknown")

        # Filtrar registros fuera de la ventana
        records = self.attempts[identificador]
        valid_records = [r for r in records if now - r[0] < self.window_seconds]
        valid_records.append((now, str(resource_id)))
        self.attempts[identificador] = valid_records

        # Contar recursos distintos intentados
        recursos_distintos = set(r[1] for r in valid_records)
        if len(recursos_distintos) >= self.threshold:
            self.blocked_until[identificador] = now + self.block_duration_seconds
            self.block_durations[identificador] = self.block_duration_seconds
            self.attempts_during_lock[identificador] = 0

            print(
                f"🚨 [seguridad-alerta-E3] ANOMALÍA: Patrón de enumeración/barrido horizontal detectado "
                f"para [{identificador}] intentando acceder a {len(recursos_distintos)} recursos distintos "
                f"({list(recursos_distintos)}) en {endpoint} en menos de {self.window_seconds}s. "
                f"Bloqueo temporal activado por {self.block_duration_seconds}s."
            )
            # Registrar en bitácora CSV
            try:
                from backend.core.security_logger import registrar_bloqueo_seguridad
                registrar_bloqueo_seguridad(
                    request=None,
                    usuario_objetivo=identificador,
                    tipo_incidente="ALERTA_E3_ENUMERACION_IDOR",
                    accion_tomada=f"SUSPENSION_TEMPORAL ({self.block_duration_seconds}s)",
                    endpoint=endpoint,
                    ip_forzada=identificador if ("." in identificador or ":" in identificador) else None,
                    device_id=device_id
                )
            except Exception as e:
                print(f"Error registrando anomalía en CSV: {e}")

            return True

        return False

    def esta_bloqueado(self, user_id_or_ip: str, penalizar_insistencia: bool = True) -> Tuple[bool, int]:
        """
        Verifica si el usuario o dispositivo se encuentra temporalmente bloqueado por comportamiento anómalo.
        Si la petición ocurre durante el bloqueo activo y penalizar_insistencia es True, duplica el tiempo de bloqueo.
        Retorna (esta_bloqueado: bool, retry_after: int).
        """
        identificador = str(user_id_or_ip or "unknown")
        now = time.time()
        bloqueado_hasta = self.blocked_until.get(identificador, 0)

        if now < bloqueado_hasta:
            if penalizar_insistencia:
                duracion_actual = self.block_durations.get(identificador, self.block_duration_seconds)
                tiempo_restante = int(bloqueado_hasta - now)
                nueva_duracion = min(7200, max(tiempo_restante * 2, duracion_actual * 2, 60))
                self.blocked_until[identificador] = now + nueva_duracion
                self.block_durations[identificador] = nueva_duracion
                self.attempts_during_lock[identificador] += 1
                retry_after = nueva_duracion

                try:
                    from backend.core.security_logger import registrar_bloqueo_seguridad
                    registrar_bloqueo_seguridad(
                        request=None,
                        usuario_objetivo=identificador,
                        tipo_incidente="REINCIDENCIA_ANOMALIA_IDOR",
                        accion_tomada=f"PENALIZACION_DUPLICADA_429 ({retry_after}s)",
                        endpoint="/anomalia-bloqueo",
                        ip_forzada=identificador if ("." in identificador or ":" in identificador) else None,
                    )
                except Exception:
                    pass

                return True, retry_after
            else:
                return True, max(1, int(bloqueado_hasta - now))

        # Limpiar si ya expiró el bloqueo
        if identificador in self.blocked_until:
            del self.blocked_until[identificador]
        if identificador in self.block_durations:
            del self.block_durations[identificador]
        if identificador in self.attempts_during_lock:
            del self.attempts_during_lock[identificador]

        return False, 0


# Instancia global del detector de anomalías
detector_anomalias = AnomalyDetector(
    threshold_distinct_resources=3,
    window_seconds=60,
    block_duration_seconds=300,
)

TODOS_LOS_LIMITADORES = [limiter_login, limiter_recuperacion, limiter_sensible, limiter_estricto]


def obtener_bloqueos_activos() -> list:
    """
    Retorna una lista con todos los bloqueos que se encuentran activos en memoria en este momento.
    """
    now = time.time()
    bloqueos = []

    # 1. Revisar Rate Limiters
    for lim in TODOS_LOS_LIMITADORES:
        for clave, info in list(lim.lockouts.items()):
            blocked_until = info.get("blocked_until", 0)
            if now < blocked_until:
                restante = max(1, int(blocked_until - now))
                partes = clave.split("_", 2)
                identificador = clave
                if len(partes) >= 3:
                    identificador = partes[2]  # El usuario o cuenta

                bloqueos.append({
                    "clave_rastreo": clave,
                    "identificador": identificador,
                    "origen": lim.name,
                    "tipo": f"Rate Limit ({lim.name})",
                    "segundos_restantes": restante,
                    "intentos_insistencia": info.get("attempts_during_lock", 0),
                    "duracion_total": info.get("lock_duration", lim.window_seconds),
                })

    # 2. Revisar Detector de Anomalías (E3)
    for id_anomalia, blocked_until in list(detector_anomalias.blocked_until.items()):
        if now < blocked_until:
            restante = max(1, int(blocked_until - now))
            bloqueos.append({
                "clave_rastreo": f"anomalia_{id_anomalia}",
                "identificador": id_anomalia,
                "origen": "Detector de Anomalías",
                "tipo": "Suspensión por Anomalía / IDOR (E3)",
                "segundos_restantes": restante,
                "intentos_insistencia": detector_anomalias.attempts_during_lock.get(id_anomalia, 0),
                "duracion_total": detector_anomalias.block_durations.get(id_anomalia, detector_anomalias.block_duration_seconds),
            })

    return bloqueos


def desbloquear_identidad(identificador: str, admin_usuario: str = "Admin") -> int:
    """
    Elimina manualmente los bloqueos activos y el historial de penalizaciones
    para un usuario, dispositivo o IP específica.
    
    Retorna el número de bloqueos eliminados.
    """
    if not identificador:
        return 0

    id_clean = identificador.strip().lower()
    total_desbloqueados = 0

    # 1. Limpiar en los Rate Limiters
    for lim in TODOS_LOS_LIMITADORES:
        claves_a_borrar = []
        for clave in list(lim.lockouts.keys()):
            if id_clean in clave.lower():
                claves_a_borrar.append(clave)

        for c in claves_a_borrar:
            lim.lockouts.pop(c, None)
            lim.history.pop(c, None)
            total_desbloqueados += 1

    # 2. Limpiar en Detector de Anomalías
    anomalias_a_borrar = []
    for k in list(detector_anomalias.blocked_until.keys()):
        if id_clean in str(k).lower():
            anomalias_a_borrar.append(k)

    for k in anomalias_a_borrar:
        detector_anomalias.blocked_until.pop(k, None)
        detector_anomalias.block_durations.pop(k, None)
        detector_anomalias.attempts_during_lock.pop(k, None)
        detector_anomalias.attempts.pop(k, None)
        total_desbloqueados += 1

    # 3. Registrar el evento de desbloqueo en la bitácora CSV de auditoría
    try:
        from backend.core.security_logger import registrar_bloqueo_seguridad
        registrar_bloqueo_seguridad(
            request=None,
            usuario_objetivo=identificador,
            tipo_incidente="DESBLOQUEO_MANUAL_ADMIN",
            accion_tomada=f"DESBLOQUEADO_POR_{admin_usuario.upper().replace(' ', '_')}",
            endpoint="/mod_principal/seguridad/desbloquear"
        )
    except Exception as e:
        print(f"Error registrando desbloqueo en CSV: {e}")

    print(f"🔓 [seguridad-admin] Identidad '{identificador}' desbloqueada manualmente por '{admin_usuario}'. ({total_desbloqueados} bloqueos eliminados)")
    return total_desbloqueados
