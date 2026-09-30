#backend.main.py
from backend.api import registro
from backend.api import login
from backend.api import usuarios
from backend.api import mod_principal
from backend.api import unidad_academica
from backend.api import matricula_sp
from backend.api import aprovechamiento_sp
from backend.api import egresados_sp
from backend.api import titulados_sp
from backend.api import recuperacion
from backend.api import programas
from backend.api.catalogos import domicilios, periodos, egresados, semaforo
from backend.core.templates import static, templates
from fastapi.staticfiles import StaticFiles as _StaticFiles

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
import os
from starlette.exceptions import HTTPException as StarletteHTTPException

app = FastAPI()

import uuid
from backend.core.rate_limiter import firmar_device_id, verificar_y_extraer_device_id

PERMITTED_COOKIES = {"session_id", "device_id"}

@app.middleware("http")
async def device_and_cookie_middleware(request: Request, call_next):
    """
    Middleware de gestión criptográfica de dispositivos y depuración de cookies:
    1. Valida la firma HMAC de la cookie 'device_id'. Si es inválida o fue manipulada en el cliente, la regenera y alerta.
    2. Si no existe, genera un nuevo identificador firmado digitalmente con clave secreta del servidor.
    3. Purga cookies obsoletas o ajenas dejando únicamente session_id y device_id.
    """
    device_cookie = request.cookies.get("device_id")
    needs_device_cookie = False
    raw_device_id = None

    if device_cookie:
        raw_device_id, fue_manipulado = verificar_y_extraer_device_id(device_cookie, request)
        if fue_manipulado or not raw_device_id:
            raw_device_id = f"dev_{uuid.uuid4().hex[:12]}"
            needs_device_cookie = True
    else:
        raw_device_id = f"dev_{uuid.uuid4().hex[:12]}"
        needs_device_cookie = True

    # Inyectar en request.state para acceso en la petición actual
    request.state.device_id = raw_device_id

    response = await call_next(request)

    # Adjuntar cookie persistente firmada criptográficamente
    if needs_device_cookie:
        signed_cookie_val = firmar_device_id(raw_device_id, request)
        response.set_cookie(
            key="device_id",
            value=signed_cookie_val,
            httponly=True,
            samesite="lax",
            max_age=31536000,  # 1 año de persistencia
            path="/",
        )

    # Purgar cualquier cookie ajena que no sea session_id o device_id
    for cookie_name in request.cookies.keys():
        if cookie_name not in PERMITTED_COOKIES:
            response.delete_cookie(cookie_name, path="/")

    return response

app.mount("/static", static)
# Montar la carpeta 'Tipografía' para servir fuentes que el equipo colocó en la raíz del proyecto
tipo_dir = os.path.join(os.path.dirname(__file__), '..', 'Tipografía')
if os.path.exists(tipo_dir):
    app.mount('/tipografia', _StaticFiles(directory=tipo_dir), name='tipografia')
app.include_router(registro.router, prefix="/registro")
app.include_router(login.router , prefix="/login")
app.include_router(usuarios.router , prefix="/usuarios")
app.include_router(mod_principal.router , prefix="/mod_principal")
app.include_router(unidad_academica.router , prefix="/unidad_academica")
app.include_router(matricula_sp.router , prefix="/matricula")
app.include_router(aprovechamiento_sp.router , prefix="/aprovechamiento")
app.include_router(egresados_sp.router , prefix="/egresados")
app.include_router(titulados_sp.router , prefix="/titulados")
app.include_router(domicilios.router)
app.include_router(periodos.router)
app.include_router(egresados.router)  # Catálogo egresados
app.include_router(semaforo.router)
app.include_router(programas.router, prefix="/programas")
app.include_router(recuperacion.router)


@app.exception_handler(StarletteHTTPException)
async def _http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Manejador global de excepciones HTTP:
    - 401: Redirige a /login para peticiones web de navegador.
    - 429: Renderiza plantilla visual con contador en tiempo real contra ataques y reintentos, o JSON con Retry-After para APIs.
    - 403: Renderiza plantilla visual de acceso denegado / violación de integridad para navegador.
    - Otros códigos: Retorna JSON o redirección según corresponda.
    """
    accept = (request.headers.get("accept") or "").lower()
    is_html_request = "text/html" in accept

    # 1. Sesión expirada o no autenticado (401) en navegador
    if exc.status_code == 401 and is_html_request:
        return RedirectResponse(url="/login", status_code=303)

    # 2. Exceso de límite de peticiones / Bloqueo activo (429) en navegador
    if exc.status_code == 429 and is_html_request:
        retry_val = 60
        if exc.headers and "Retry-After" in exc.headers:
            try:
                retry_val = int(exc.headers["Retry-After"])
            except (ValueError, TypeError):
                retry_val = 60

        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "status_code": 429,
                "retry_after": retry_val,
                "error_message": exc.detail or f"Demasiadas solicitudes. Por favor espere {retry_val} segundos antes de intentar nuevamente.",
                "redirect_url": "/login" if "/login" in request.url.path else "/mod_principal/",
            },
            status_code=429,
            headers=dict(exc.headers or {}),
        )

    # 3. Acceso denegado o prohibido (403) en navegador
    if exc.status_code == 403 and is_html_request:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "status_code": 403,
                "retry_after": 0,
                "error_message": exc.detail or "Acceso denegado: No cuenta con los privilegios institucionales necesarios.",
                "redirect_url": "/login" if "/login" in request.url.path else "/mod_principal/",
            },
            status_code=403,
            headers=dict(exc.headers or {}),
        )

    # 4. Respuesta JSON estándar para APIs o solicitudes asíncronas
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=dict(exc.headers or {}),
    )

@app.get("/favicon.ico")
async def favicon():
    favicon_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "static", "favicon.ico")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path, media_type="image/x-icon")
    return RedirectResponse(url="/static/favicon.ico")


@app.get("/sicae-logo.png")
async def sicae_logo():
    logo_path = os.path.join(os.path.dirname(__file__), "..", "SiCAE Logo.png")
    if os.path.exists(logo_path):
        return FileResponse(logo_path, media_type="image/png")
    return JSONResponse(status_code=404, content={"detail": "Logo no encontrado"})

@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/login")


@app.get("/logout")
async def logout_legacy_redirect():
    return RedirectResponse(url="/login/logout", status_code=303)