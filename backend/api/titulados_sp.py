from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text 
from sqlalchemy import select
from collections import defaultdict

from backend.api import unidad_academica
from backend.database.connection import get_db
from backend.core.templates import templates
from backend.schemas import Nivel
from backend.services.titulados_service import obtener_titulados, preparar_datos_temp_titulados, preparar_datos_temp_titulados_desde_db, procesar_titulados
from backend.crud.ConsultaTitulados import insertar_temp_titulados, insertar_titulados_sp, finalizar_captura_programa_modalidad, verificar_todos_programas_finalizados, finalizar_unidad_academica
from backend.services.periodo_service import get_periodo_activo, get_periodo_anterior_al_ultimo, get_ultimo_periodo
from backend.core.auth import get_current_session
from backend.database.models.CatPeriodo import CatPeriodo as Periodo
from backend.database.models.Temp_Titulados import Temp_Titulados as TituladosModel
from backend.database.models.CatUnidadAcademica import CatUnidadAcademica as Unidad_Academica
from backend.database.models.Usuario import Usuario
from backend.database.models.SemaforoUnidadAcademica import SemaforoUnidadAcademica
from backend.database.models.CatRoles import CatRoles
from backend.database.models.CatNivel import CatNivel as Nivel
from backend.database.models.UnidadProgramaModalidad import CatUnidadProgramaModalidad
from backend.database.models.CatProgramas import CatProgramas
from backend.database.models.ProgramaModalidad import ProgramaModalidad
from backend.database.models.Validacion import Validacion
from pydantic import BaseModel
from typing import List, Optional
from backend.utils.request import get_request_host
import traceback

host = "Test"
fila = []

class FinalizarTituladosRequest(BaseModel):
    datos: Optional[List[dict]] = []
    programa: str
    modalidad: str
    origen: str

def valor_orden_edad(edad: str):
    edad = edad.strip()

    if edad.startswith("<="):
        return int(edad.replace("<=", "")) - 0.5

    if edad.startswith(">="):
        return int(edad.replace(">=", "")) + 0.5

    if edad.startswith("<"):
        return int(edad.replace("<", "")) - 0.5

    if edad.startswith(">"):
        return int(edad.replace(">", "")) + 0.5

    if "-" in edad:
        inicio = edad.split("-")[0]
        return int(inicio)

    return int(edad)

router = APIRouter()

@router.get("/consulta", response_class=HTMLResponse)
async def consulta_titulados(
    request: Request,
    sess = Depends(get_current_session),
    db: Session = Depends(get_db)
):
    
    id_rol = int(sess.id_rol)
    nombre_rol = sess.nombre_rol
    
    nombre = sess.nombre_usuario
    apellidoP_usuario = sess.apellidoP_usuario
    apellidoM_usuario = sess.apellidoM_usuario
    
    nombre_usuario = sess.usuario
    sigla_unidad_academica = sess.sigla_unidad_academica
    id_unidad_academica = int(sess.id_unidad_academica)
    nombre_nivel = sess.nombre_nivel
    ua_usuario = None
    unidad_academica_usuario = None

    if id_unidad_academica > 0:
            ua_usuario = db.query(Unidad_Academica).filter(
                Unidad_Academica.Id_Unidad_Academica == id_unidad_academica
            ).first()

    if ua_usuario:
        unidad_academica_usuario = ua_usuario.Nombre
    else:
        print(f"Advertencia: No se encontró la Unidad Académica con ID {id_unidad_academica} para el usuario {nombre_usuario}.")

    nivel = sess.id_nivel

    print(unidad_academica_usuario)
    """
    unidad_academica = sess.unidad_academica
   
    nombre_nivel = getattr(sess, 'nombre_nivel', "Nivel de Prueba")
    nivel_acceso = getattr(sess, 'id_nivel', 0)
    usuario = getattr(sess, 'usuario', "usuario_prueba")"""

    print(f"Usuario: {nombre_usuario}, Rol: {nombre_rol} (ID: {id_rol}), Unidad Académica: {unidad_academica} ({sigla_unidad_academica}), Nivel: {nombre_nivel}, Host: {host}")
    try:
        periodo_id, periodo_literal = get_periodo_anterior_al_ultimo(db)
        periodo_id_actual, periodo_literal_actual = get_periodo_activo(db)
        if not periodo_id or not periodo_literal:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error_message": "No hay un periodo activo configurado en el sistema.",
                "redirect_url": "/mod_principal/",
                "session": sess
            })
        
        periodo_default_literal = periodo_literal

        print(f" Periodo por defecto: {periodo_default_literal}")


    except Exception as e:
        print(f" Error al obtener periodo: {str(e)}")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_message": f"Error al cargar el periodo: {str(e)}",
            "redirect_url": "/mod_principal/",
            "session": sess
        })

    roles_permitidos = [1, 3, 4, 5, 6, 7, 8, 9]  #1=Admin, 3=Capturista, 4-9=Roles de validación/rechazo
    if id_rol not in roles_permitidos:
        if id_rol != 0:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error_message": f"Acceso denegado: Su rol ({nombre_rol}) no tiene permisos para acceder a esta funcionalidad.",
                "redirect_url": "/mod_principal/",
                "session": sess
            })
        else:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error_message": "Acceso denegado: No se ha identificado un rol válido. Por favor, inicie sesión.",
                "redirect_url": "/login/",
                "session": sess
            })
    

    es_capturista = (id_rol == 3)
    es_validador = (id_rol in [4, 5, 6, 7, 8, 9])  
    es_rol_director = (id_rol in [4, 5])  
    es_rol_superior = (id_rol in [6, 7, 8, 9])  
    modo_vista = "captura" if es_capturista else "validacion"

    periodos = []

    periodos = db.query(Periodo).order_by(Periodo.Id_Periodo.desc()).all()
    
    niveles = db.query(Nivel).filter(Nivel.Id_Estatus == 1).order_by(Nivel.Id_Nivel).all()
    

    query = (
        select(Unidad_Academica.Sigla , Unidad_Academica.Nombre, Nivel.Nivel)
        .distinct()
        .join(CatUnidadProgramaModalidad, CatUnidadProgramaModalidad.Id_Unidad_Academica == Unidad_Academica.Id_Unidad_Academica)
        .join(ProgramaModalidad, ProgramaModalidad.Id_Modalidad_Programa == CatUnidadProgramaModalidad.Id_Modalidad_Programa)
        .join(CatProgramas, CatProgramas.Id_Programa == ProgramaModalidad.Id_Programa)
        .join(Nivel, Nivel.Id_Nivel == CatProgramas.Id_Nivel)
        .order_by(Nivel.Nivel.desc())
    )

    rows = db.execute(query).all()

    resultado = defaultdict(list)
    for sigla, nombre, nivel in rows:
        resultado[nivel].append({"sigla": sigla, "nombre": nombre})
    resultado = dict(resultado)

    periodosDisponibles = [periodo.Periodo for periodo in periodos]
    nombres_niveles = [n.Nivel for n in niveles]
    print()

    print("Todos los periodos:")
    print(periodosDisponibles)

    print()


    print("Todas las unidades:")
    print(resultado)

    contexto = {}
    filas = []

    if not es_validador:
        try:
            print(
                f"Obteniendo titulados para UA: {sigla_unidad_academica}, "
                f"Periodo: {periodo_default_literal}, "
                f"Nivel: {nombre_nivel}, "
                f"Usuario: {nombre_usuario}"
            )

            contexto, filas = obtener_titulados(
                db=db,
                unidad_academica=sigla_unidad_academica,
                periodo=periodo_literal_actual,
                nivel=nombre_nivel,
                usuario=nombre_usuario,
                host=host,
            )

            if filas is None:
                filas = []

        except Exception as e:
            print(f"Error obteniendo titulados: {e}")

            contexto = {}
            filas = []

    try:
        boleta = contexto.get("Boleta")

        if boleta:
            boleta = int(boleta)
            boletas = list(range(boleta + 12, boleta , -1))

        print(f"Boletas obtenidas: {boletas}")

    except Exception as e:

        print(f"Error calculando boletas: {e}")
        boletas = []

    try:
        edades = set(
            fila["Grupo_Edad"]
            for fila in filas
            if fila.get("Grupo_Edad")
        )
        print(f"Edades únicas sin ordenar: {edades}")

        edades_ordenadas = sorted(edades, key=valor_orden_edad)

        print(f"Edades únicas encontradas: {edades_ordenadas}")

    except Exception as e:

        print(f"Error procesando edades: {e}")
        edades_ordenadas = []
   
   # print(f"Contexto final: {contexto}")                
    return templates.TemplateResponse(
            "titulados_consulta.html", 
            {"request": request,
             "nombre_usuario": nombre_usuario,
             "periodo_default_literal": periodo_default_literal,
             "periodos" : periodosDisponibles,
             "niveles" : nombres_niveles,
             "unidades": resultado,
             "unidad_academica" : unidad_academica_usuario,
             "sigla_unidad_academica" : sigla_unidad_academica,
             "nombre_rol": nombre_rol,
             "nivel_acceso" : nivel,
             "nombre_nivel" : nombre_nivel,
             "contexto": contexto,
             "boletas": boletas,
             "filas": filas,
             "edades" : edades_ordenadas,
             "es_capturista": es_capturista,
             "es_validador": es_validador,
             "es_rol_superior": es_rol_superior,
             "es_rol_director": es_rol_director,
             "acceso_restringido" : False,
             "session": sess}
             )

@router.post("/guardar-avance-titulados", response_class=JSONResponse)
def guardar_titulados(
    datos: List[dict],
    sess = Depends(get_current_session),
    db: Session = Depends(get_db)):

    sigla_unidad_academica = sess.sigla_unidad_academica
    nivel = sess.nombre_nivel

    try:
        id_p, periodo = get_periodo_anterior_al_ultimo(db)
        id_p_actual, periodo_actual = get_periodo_activo(db)

        if periodo is None:
            return JSONResponse(
                content={"status": "error", "message": "No se encontró un periodo activo."}, 
                status_code=404
            )
    
    except Exception as e:
        print(f"Error al obtener periodo activo: {str(e)}")
        return JSONResponse(content={"status": "error", "message": f"Error al obtener periodo activo: {str(e)}"}, status_code=500)

    print(f"Datos recibidos para guardar: {datos}")

    try:
        registros = preparar_datos_temp_titulados(
            datos=datos,
            periodo = periodo,
            sigla= sigla_unidad_academica,
            nivel= nivel
        )

       # print(f"Registros preparados para guardar: {registros}")

        total = insertar_temp_titulados(db, registros)

        #insertar en titulados

        insertar_titulados_sp(db, sigla_unidad_academica, sess.usuario, host, periodo_actual, nivel)
 
    except Exception as e:
        print(f"Error preparando datos para guardar: {e}")
        return JSONResponse(content={"status": "error", "message": f"Error preparando datos: {str(e)}"}, status_code=500)
    
    return {"status": "guardado", "total_registros": total}


@router.post("/finalizar-titulados", response_class=JSONResponse)
def finalizar_captura_titulados(
    payload: FinalizarTituladosRequest,
    sess=Depends(get_current_session),
    db: Session = Depends(get_db)
):
    datos     = payload.datos
    programa  = payload.programa
    modalidad = payload.modalidad
    sigla     = sess.sigla_unidad_academica
    nivel     = sess.nombre_nivel

    try:
        id_p,        periodo        = get_periodo_anterior_al_ultimo(db)
        id_p_actual, periodo_actual = get_periodo_activo(db)
        if periodo is None or periodo_actual is None:
            return JSONResponse(
                content={"status": "error", "message": "No se encontró un periodo activo."},
                status_code=404
            )
    except Exception as e:
        return JSONResponse(
            content={"status": "error", "message": f"Error al obtener periodo activo: {str(e)}"},
            status_code=500
        )

    # Preparar registros fuera de cualquier condición para que siempre exista la variable
    registros = []
    if datos:
        try:
            if payload.origen == "db":
                registros = preparar_datos_temp_titulados_desde_db(
                    datos=datos,
                    periodo=periodo,
                    sigla=sigla,
                    nivel=nivel
                )
            else:
                registros = preparar_datos_temp_titulados(
                    datos=datos,
                    periodo=periodo,
                    sigla=sigla,
                    nivel=nivel
                )
        except Exception as e:
            return JSONResponse(
                content={"status": "error", "message": f"Error al preparar datos: {str(e)}"},
                status_code=500
            )

    try:
        # 1. Insertar en Temp_Titulados si hay registros
        if registros:
            insertar_temp_titulados(db, registros)

        # 2. SP programa-modalidad (borra Temp_Titulados al terminar)
        finalizar_captura_programa_modalidad(
            db, periodo_actual, sigla,
            modalidad, programa, sess.usuario, host, nivel
        )

        # 3. Verificar si todos los programas-modalidad de la UA están en semáforo 3
        todos_finalizados = verificar_todos_programas_finalizados(
            db, periodo, sigla, nivel
        )


        # 4. Si todos están en 3, reinsertar y ejecutar SP de unidad académica
        if todos_finalizados:
            if registros:
                db.expunge_all()  
                insertar_temp_titulados(db, registros)
            
            else:
                print("No hay registros para reinsertar antes de finalizar unidad académica.")

            finalizar_unidad_academica(
                db, periodo, sigla, modalidad, programa,
                sess.usuario, host, nivel
            )
            

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            content={"status": "error", "message": f"Error al finalizar captura: {str(e)}"},
            status_code=500
        )

    return JSONResponse(
        content={
            "status": "finalizado",
            "unidad_finalizada": todos_finalizados
        }
    )

@router.get('/acuse-validacion')
async def acuse_titulados_view(
    request: Request,
    periodo: str,
    nivel: str,
    unidad: str,
    sess = Depends(get_current_session),
    db: Session = Depends(get_db),
    exportando_pdf: bool = False
):
    
    try:
       
        id_p_actual, periodo_actual = get_periodo_activo(db)

        if periodo is None:
            return JSONResponse(
                content={"status": "error", "message": "No se encontró un periodo activo."}, 
                status_code=404
            )
    
    except Exception as e:
        print(f"Error al obtener periodo activo: {str(e)}")
        return JSONResponse(content={"status": "error", "message": f"Error al obtener periodo activo: {str(e)}"}, status_code=500)

    
    print(f"Generando acuse para Unidad: {unidad}, Periodo: {periodo_actual}, Nivel: {nivel}, Usuario: {sess.usuario}, Host: {host}")



    contexto_sp, filas = obtener_titulados(db, unidad, periodo_actual, nivel, sess.usuario, host)
    

    #print (f"Contexto SP: {contexto_sp}")
    #print (f"Filas SP: {filas}")

    tablas = procesar_titulados(filas)

    print ("Muchas tablas")

    nombre_nivel = sess.nombre_nivel
    id_rol = int(sess.id_rol)
    nombre_capturista = "No definido."
    nombre_ceget = "No definido."
    nombre_titular = "No definido."
    Id_Unidad_Academica = int(sess.id_unidad_academica)

    # 2. Hacemos la consulta agregando Usuario.Id_Rol
    usuarios = db.query(Usuario.Nombre, Usuario.Paterno, Usuario.Materno, Usuario.Id_Rol).filter(
        Usuario.Id_Unidad_Academica == Id_Unidad_Academica,
        Usuario.Id_Estatus == 1
    ).all()

    # 3. Recorremos los resultados y asignamos según el Id_Rol
    for u in usuarios:
        # Construimos el nombre completo de una vez
        nombre_completo = f"{u.Nombre} {u.Paterno} {u.Materno}".strip()
        
        if u.Id_Rol == 3:
            nombre_capturista = nombre_completo
        elif u.Id_Rol == 4:
            nombre_ceget = nombre_completo
        elif u.Id_Rol == 5:
            nombre_titular = nombre_completo
    periodo_anterior_id, _ = get_periodo_anterior_al_ultimo(db)
    print("EK* id:",periodo_anterior_id)
    
    id_nivel = str(sess.id_nivel)

    print("Nivle: ", id_nivel)
    
    semaforo_captura = db.query(SemaforoUnidadAcademica).filter(
        SemaforoUnidadAcademica.Id_Periodo == periodo_anterior_id,
        SemaforoUnidadAcademica.Id_Unidad_Academica == Id_Unidad_Academica,
        SemaforoUnidadAcademica.Id_Formato == 2,
        SemaforoUnidadAcademica.Id_Nivel == id_nivel
    ).first()
    
    print("Semaforo Captura:", semaforo_captura)

    semaforo = 0

    if semaforo_captura:
        semaforo = semaforo_captura.Id_Semaforo
        print("Semaforo:",semaforo)
    
    print("Semaforo:", semaforo)

    no_validado = semaforo < 9


    puede_validar = False
    usuario_ya_valido = False
    usuario_ya_rechazo = False
    esperando_por_rol = None

    try:
        if id_rol in [4, 5, 6, 7, 8, 9] and periodo_anterior_id is not None:
            semaforo_unidad = db.query(SemaforoUnidadAcademica).filter(
                SemaforoUnidadAcademica.Id_Periodo == periodo_anterior_id,
                SemaforoUnidadAcademica.Id_Unidad_Academica == int(sess.id_unidad_academica),
                SemaforoUnidadAcademica.Id_Formato == 4  # Formato 4 = Titulados
            ).first()

            estado_semaforo = semaforo_unidad.Id_Semaforo if semaforo_unidad else None

            # Regla de jerarquía real (alineada a los SPs de Validar/Rechazar):
            # SP_Valida_Titulados y SP_Rechaza_Titulados validan que:
            #   sua.Id_Semaforo == (Id_Rol del usuario) - 1
            # Esto permite pasos distintos para 6,7,8,9 en vez de agruparlos.
            semaforo_esperado = id_rol - 1

            if estado_semaforo is not None:
                if estado_semaforo == semaforo_esperado:
                    puede_validar = True
                    usuario_ya_valido = False
                    usuario_ya_rechazo = False
                elif estado_semaforo > semaforo_esperado:
                    usuario_ya_valido = True
                else:
                    # Aún no toca este nivel
                    puede_validar = False
                    try:
                        # El primer rol por defecto debe ser Capturista (Id_Rol 2)
                        # Si el semáforo está en 1 o 2, está esperando al Capturista
                        if estado_semaforo in [1, 2]:
                            esperando_por_rol = "Capturista"
                        else:
                            rol_esperado_id = int(estado_semaforo) + 1
                            rol_obj = db.query(CatRoles).filter(CatRoles.Id_Rol == rol_esperado_id).first()
                            esperando_por_rol = rol_obj.Rol if rol_obj else "Capturista"
                    except Exception:
                        esperando_por_rol = "Capturista"
            else:
                # Si no hay semáforo configurado, el primer paso siempre es Capturista
                esperando_por_rol = "Capturista"

            # Si ya rechazó, ocultar botones (salvo que el semáforo esté justo en el nivel esperado)
            try:
                id_usuario_actual = int(sess.id_usuario)
                rechazo_usuario = db.query(Validacion).filter(
                    Validacion.Id_Periodo == periodo_anterior_id,
                    Validacion.Id_Usuario == id_usuario_actual,
                    Validacion.Id_Formato == 4,
                    Validacion.Validado == 0
                ).first()
                if rechazo_usuario:
                    if not puede_validar:
                        usuario_ya_rechazo = True
            except Exception:
                # Si algo falla aquí, no bloqueamos por seguridad de UI
                pass
    except Exception:
        # Si algo falla, solo no mostramos estado (UI seguirá normal)
        pass



    return templates.TemplateResponse("titulados_acuse.html", {
        "request"       : request,
        "periodo"       : contexto_sp.get("Periodo"),
        "unidad"        : contexto_sp.get("Sigla"),
        "nivel"         : nombre_nivel,
        "exportando_pdf": exportando_pdf,
        "nombre_capturista" : nombre_capturista,
        "nombre_ceget"  : nombre_ceget,
        "nombre_titular": nombre_titular,
        "no_validado"   : no_validado,
        "id_rol"        : id_rol,
        "puede_validar" : puede_validar,
        "usuario_ya_valido" : usuario_ya_valido,
        "usuario_ya_rechazo": usuario_ya_rechazo,
        "esperando_por_rol": esperando_por_rol,
        "session": sess,
        **tablas
           # desempaca todas las tablas directamente
    })



@router.post('/validar')
async def validar_titulados(request: Request, sess=Depends(get_current_session), db: Session = Depends(get_db)):
    """
    Valida los datos de Titulados.
    Ejecuta el SP [dbo].[SP_Valida_Titulados] (Formato 4) para avanzar semáforo y registrar en Validacion.
    """
    try:
        # NOTA: Evitamos hacer await request.json() dos veces seguidas para no congelar la petición
        body = await request.json()
        
        # 1. Valores reales enviados desde la interfaz HTML/JS
        periodo_in = body.get("periodo")
        unidad_in = body.get("unidad")    # 👈 El nombre/sigla de la escuela que estás viendo
        nivel_in = body.get("nivel")      # 👈 El nivel que estás viendo

        nota_in = (body.get('nota') or '').strip()

        # Datos de la sesión del usuario que da click
        id_rol = int(sess.id_rol)
        usuario_sp = sess.usuario or 'sistema'
        _,periodo_literal = get_periodo_activo(db)
        host_sp = get_request_host(request)

        # Roles permitidos
        if id_rol not in [4, 5, 6, 7, 8, 9]:
            return {"success": False, "message": "Solo roles de validación pueden ejecutar esta acción."}

        if periodo_in is None:
            return {"success": False, "message": "No se recibió el periodo."}



        # 2. STRATEGY FALLBACK: Priorizar lo que viene de la pantalla, si no, usar sesión
        unidad_sigla = (unidad_in or sess.sigla_unidad_academica or '').strip()
        if not unidad_sigla and hasattr(sess, 'id_unidad_academica'):
            try:
                ua = db.query(Unidad_Academica).filter(Unidad_Academica.Id_Unidad_Academica == int(sess.id_unidad_academica)).first()
                unidad_sigla = ua.Sigla if ua else ''
            except Exception:
                unidad_sigla = ''

        if not unidad_sigla:
            return {"success": False, "message": "No se pudo resolver la Unidad Académica."}

        nivel_literal = (nivel_in or sess.nombre_nivel or '').strip()
        if not nivel_literal and hasattr(sess, 'id_nivel'):
            nivel_literal = str(sess.id_nivel)

        nota_sp = nota_in or f"Validado por {sess.nombre_completo}"

        # Intentar obtener semáforo para monitoreo
        try:
            periodo_id_db , _ = get_periodo_anterior_al_ultimo(db)
            sem = db.query(SemaforoUnidadAcademica).filter(
                SemaforoUnidadAcademica.Id_Periodo == periodo_id_db,
                SemaforoUnidadAcademica.Id_Unidad_Academica == int(sess.id_unidad_academica),
                SemaforoUnidadAcademica.Id_Formato == 4,
            ).first()
            sem_actual = sem.Id_Semaforo if sem else None
        except Exception:
            sem_actual = None

        # 🔍 IMPRESIÓN DETALLADA ANTES DE EXECUTAR EL SP
        print(f"\n🚀 {'='*60}")
        print("📊 PREPARANDO EJECUCIÓN DE STORED PROCEDURE")
        print(f"{'='*60}")
        print(f" SQL: EXEC [dbo].[SP_Valida_Titulados]")
        print(f" 🔹 @PPeriodo          = '{periodo_literal}' (Origen: {periodo_in})")
        print(f" 🔹 @UUnidad_Academica = '{unidad_sigla}' (Origen JS: '{unidad_in}' | Sess: '{sess.sigla_unidad_academica}')")
        print(f" 🔹 @NNivel            = '{nivel_literal}' (Origen JS: '{nivel_in}' | Sess: '{sess.nombre_nivel}')")
        print(f" 🔹 @uusuario          = '{usuario_sp}'")
        print(f" 🔹 @HHost             = '{host_sp}'")
        print(f" 🔹 @NNota             = '{nota_sp}'")
        print(f" [DEBUG] Semáforo actual ID en DB: {sem_actual}")
        print(f"{'='*60}\n")

        sql = text("""
            EXEC [dbo].[SP_Valida_Titulados]
                @PPeriodo = :periodo,
                @UUnidad_Academica = :ua,
                @NNivel = :nivel,
                @uusuario = :usuario,
                @HHost = :host,
                @NNota = :nota
        """)

        # Ejecución
        result = db.execute(sql, {
            'periodo': periodo_literal,
            'ua': unidad_sigla,
            'nivel': nivel_literal,
            'usuario': usuario_sp,
            'host': host_sp,
            'nota': nota_sp,
        })

        db.commit()
        print("✅ [DB] Commit ejecutado de forma exitosa.")

        return {"success": True, "message": "Titulados validados correctamente"}
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error crítico al validar Titulados: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    

@router.post('/rechazar')
async def rechazar_titulados(request: Request, sess=Depends(get_current_session), db: Session = Depends(get_db)):
    """
    Rechaza los datos de Titulados.
    Ejecuta el SP [dbo].[SP_Rechaza_Titulados] (Formato 4) para regresar semáforo y registrar en Validacion.
    """
    try:
        data = await request.json()
        periodo_in = data.get('periodo')
        unidad_in = data.get('unidad')  
        nivel_in = data.get('nivel')    
        motivo = (data.get('motivo') or '').strip()

        periodo_in = data.get('periodo')
        motivo = (data.get('motivo') or '').strip()
        _,periodo_literal = get_periodo_activo(db)

        if not motivo:
            raise HTTPException(status_code=400, detail="Debe proporcionar un motivo de rechazo")

        # Respetar nvarchar(250)
        if len(motivo) > 250:
            motivo = motivo[:250]

        # Sesión
        id_rol = int(sess.id_rol)
        usuario_sp = sess.usuario or 'sistema'
        unidad_sigla = (sess.sigla_unidad_academica or '').strip()
        nivel_literal = (sess.nombre_nivel or '').strip()
        host_sp = get_request_host(request)

        if id_rol not in [4, 5, 6, 7, 8, 9]:
            return {"success": False, "message": "Solo roles de validación pueden ejecutar esta acción."}

        if periodo_in is None:
            return {"success": False, "message": "No se recibió el periodo."}


        if not unidad_sigla:
            try:
                ua = db.query(Unidad_Academica).filter(Unidad_Academica.Id_Unidad_Academica == int(sess.id_unidad_academica)).first()
                unidad_sigla = ua.Sigla if ua else ''
            except Exception:
                unidad_sigla = ''

        if not unidad_sigla:
            return {"success": False, "message": "No se pudo resolver la Unidad Académica."}

        if not nivel_literal:
            nivel_literal = str(sess.id_nivel)

        print(f"\n{'='*60}")
        print("🔴 RECHAZAR TITULADOS (SP_Rechaza_Titulados)")
        print(f"Usuario: {usuario_sp} | Rol: {id_rol}")
        print(f"Periodo: {periodo_literal} | UA: {unidad_sigla} | Nivel: {nivel_literal}")
        print(f"Host: {host_sp}")
        print(f"Motivo: {motivo}")
        print(f"{'='*60}\n")

        sql = text("""
            EXEC [dbo].[SP_Rechaza_Titulados]
                @PPeriodo = :periodo,
                @UUnidad_Academica = :ua,
                @NNivel = :nivel,
                @UUsuario = :usuario,
                @HHost = :host,
                @NNota = :nota
        """)

        db.execute(sql, {
            'periodo': periodo_literal,
            'ua': unidad_sigla,
            'nivel': nivel_literal,
            'usuario': usuario_sp,
            'host': host_sp,
            'nota': motivo,
        })

        db.commit()

        return {"success": True, "message": "Titulados rechazados. Se notificará al capturista."}
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error al rechazar Titulados: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
