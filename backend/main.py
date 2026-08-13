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
from backend.api.catalogos import domicilios, periodos, egresados
from backend.core.templates import static
from fastapi.staticfiles import StaticFiles as _StaticFiles

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
import os
from starlette.exceptions import HTTPException as StarletteHTTPException

app = FastAPI()

@app.middleware("http")
async def cookie_cleanup_middleware(request: Request, call_next):
    response = await call_next(request)
    # Detectar y purgar cualquier cookie que no sea estrictamente session_id
    for cookie_name in request.cookies.keys():
        if cookie_name != "session_id":
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
app.include_router(egresados.router)



app.include_router(recuperacion.router)


@app.exception_handler(StarletteHTTPException)
async def _http_exception_handler(request: Request, exc: StarletteHTTPException):
    # For browser requests, redirect to login on 401.
    accept = (request.headers.get("accept") or "").lower()
    if exc.status_code == 401 and "text/html" in accept:
        return RedirectResponse(url="/login", status_code=303)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

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