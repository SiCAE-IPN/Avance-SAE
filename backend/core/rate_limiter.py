# backend/core/rate_limiter.py
import time
from collections import defaultdict
from fastapi import Request, HTTPException, status

class InMemoryRateLimiter:
    """
    Rate Limiter en memoria basado en ventana deslizante (Sliding Window).
    Protege endpoints sensibles (login, recuperación de contraseña, firmas y validaciones)
    contra ataques de fuerza bruta, enumeración y sobrecarga DoS.
    """
    def __init__(self, requests_limit: int = 10, window_seconds: int = 60):
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        self.history = defaultdict(list)

    async def __call__(self, request: Request):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        
        # Limpiar registros antiguos fuera de la ventana de tiempo
        timestamps = self.history[client_ip]
        self.history[client_ip] = [t for t in timestamps if now - t < self.window_seconds]
        
        # Verificar si supera el límite permitido
        if len(self.history[client_ip]) >= self.requests_limit:
            retry_after = int(self.window_seconds - (now - self.history[client_ip][0]))
            print(f"[seguridad] Alerta Rate Limit: IP {client_ip} excedió el límite en {request.url.path}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Demasiadas solicitudes. Límite de {self.requests_limit} peticiones por minuto alcanzado. Intente de nuevo en {max(1, retry_after)} segundos.",
                headers={"Retry-After": str(max(1, retry_after))}
            )
            
        self.history[client_ip].append(now)

# Limitadores preconfigurados para endpoints críticos
limiter_login = InMemoryRateLimiter(requests_limit=10, window_seconds=60)         # 10 intentos por minuto
limiter_recuperacion = InMemoryRateLimiter(requests_limit=5, window_seconds=60)   # 5 intentos por minuto
limiter_sensible = InMemoryRateLimiter(requests_limit=30, window_seconds=60)      # 30 solicitudes por minuto

class AnomalyDetector:
    """
    Detector de patrones anómalos y enumeración horizontal.
    Monitorea si un usuario o IP intenta acceder consecutivamente a múltiples recursos no autorizados.
    """
    def __init__(self, threshold_distinct_resources: int = 3, window_seconds: int = 60):
        self.threshold = threshold_distinct_resources
        self.window_seconds = window_seconds
        self.attempts = defaultdict(list)

    def registrar_intento_no_autorizado(self, user_id_or_ip: str, resource_id: str, endpoint: str):
        now = time.time()
        records = self.attempts[user_id_or_ip]
        self.attempts[user_id_or_ip] = [r for r in records if now - r[0] < self.window_seconds]
        self.attempts[user_id_or_ip].append((now, resource_id))

        recursos_distintos = set(r[1] for r in self.attempts[user_id_or_ip])
        if len(recursos_distintos) >= self.threshold:
            print(f"🚨 [seguridad-alerta] ANOMALÍA: Patrón de enumeración/barrido horizontal detectado para [{user_id_or_ip}] intentando acceder a {len(recursos_distintos)} recursos distintos ({list(recursos_distintos)}) en {endpoint} en menos de {self.window_seconds}s!")

detector_anomalias = AnomalyDetector(threshold_distinct_resources=3, window_seconds=60)
