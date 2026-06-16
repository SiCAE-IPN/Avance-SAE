
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Any
import pyodbc
from backend.database.connection import get_db
from backend.database.models.Temp_Titulados import Temp_Titulados
import time

def get_titulados(
    db: Session,
    unidad_academica: str,
    periodo: str,
    nivel: str,
    usuario: str,
    host: str
) -> List[Dict[str, Any]]:

    try:
        # Obtener la conexión pyodbc cruda desde SQLAlchemy
        connection = db.connection().connection

        cursor = connection.cursor()

        cursor.execute("""
            EXEC [dbo].[SP_Consulta_Titulados_Unidad_Academica]
                @UUnidad_Academica = ?,
                @Pperiodo          = ?,
                @NNivel            = ?,
                @UUsuario          = ?,
                @HHost             = ?
        """, (unidad_academica, periodo, nivel, usuario, host))

       
        rows = []
        while True:
            try:
                columns = [col[0] for col in cursor.description]
                rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
                if rows:
                    break
            except TypeError:
                
                pass

            if not cursor.nextset():
                break

        cursor.close()
        return rows

    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Error al ejecutar SP_Consulta_Titulados_Unidad_Academica: {e}")
    
def insertar_temp_titulados(db: Session, registros: list[Temp_Titulados]) -> int:
    try:
        if not registros:
            return 0
        
        datos = [
            {c.name: getattr(r, c.name) for c in r.__table__.columns}
            for r in registros
        ]

        
        db.execute(Temp_Titulados.__table__.insert(), datos)
        db.commit()
        
        return len(datos)
    except Exception as e:
        db.rollback()
        raise e
    
def insertar_titulados_sp(db: Session, unidad_academica, usuario, host, periodo, nivel):
    try:
        connection = db.connection().connection
        cursor = connection.cursor()
        cursor.execute("""
            EXEC [dbo].[SP_Actualiza_Titulados_Por_Unidad_Academica]
                @UUnidad_Academica = ?,
                @UUsuario          = ?,
                @HHost             = ?,       
                @Pperiodo          = ?,
                @NNivel            = ?
        """, (unidad_academica, usuario, host, periodo, nivel))
        
        connection.commit()
        cursor.close()

    except Exception as e:
        connection.rollback()
        raise RuntimeError(f"Error al ejecutar SP_Insertar_Titulados: {e}")

def finalizar_captura_programa_modalidad(db: Session, periodo,unidad_academica, modalidad, programa, usuario, host, nivel):

    try:
        connection = db.connection().connection
        cursor = connection.cursor()
        cursor.execute(
            """Exec [dbo].[SP_Actualiza_Titulados_Por_Semestre_AU] 
                    @PPeriodo = ?
                    , @UUnidad_Academica = ?
                    , @MModalidad = ?
                    , @PPrograma = ?
                    , @UUsuario = ?
                    , @HHost = ?
                    , @NNivel = ? """
            , (periodo, unidad_academica, modalidad, programa, usuario, host, nivel))

        connection.commit()
        cursor.close()

    except Exception as e:
        connection.rollback()
        raise RuntimeError(f"Error al ejecutar SP_Finalizar_Captura {e}")
    
def verificar_todos_programas_finalizados(
    db: Session,
    periodo: str,
    sigla: str,
    nivel: str
) -> bool:
    
    resultado = db.execute(
        text("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN ssua.id_semaforo = 3 THEN 1 ELSE 0 END) as finalizados
            FROM [dbo].[Semaforo_Semestre_Unidad_Academica] ssua
                INNER JOIN [dbo].[Cat_Periodo] per
                    ON per.Id_Periodo = ssua.Id_Periodo
                INNER JOIN [dbo].[Cat_Unidad_Academica] ua
                    ON ua.Id_Unidad_Academica = ssua.Id_Unidad_Academica
                INNER JOIN [dbo].[Cat_Nivel] niv
                    ON niv.Id_Nivel = ssua.Id_Nivel
            WHERE per.Periodo   = :periodo
              AND ua.Sigla      = :sigla
              AND niv.Nivel     = :nivel
              AND ssua.Id_Formato = 4
        """),
        {"periodo": periodo, "sigla": sigla, "nivel": nivel}
    ).fetchone()

    if resultado is None or resultado.total == 0:
        return False

    return resultado.total == resultado.finalizados

def finalizar_unidad_academica(
    db: Session,
    periodo: str,
    sigla: str,
    modalidad, 
    programa, 
    usuario,
    host, 
    nivel
):
    try:
        connection = db.connection().connection
        cursor = connection.cursor()
        cursor.execute(
            """Exec [dbo].[SP_Finaliza_Captura_Titulados] 
                    @PPeriodo = ?
                    , @UUnidad_Academica = ?
                    , @MModalidad = ?
                    , @PPrograma = ?
                    , @UUsuario = ?
                    , @HHost = ?
                    , @NNivel = ? """
            , (periodo, sigla, modalidad, programa,usuario, host, nivel))

        connection.commit()
        cursor.close()

    except Exception as e:
        connection.rollback()
        raise RuntimeError(f"Error al ejecutar SP_Finalizar_Unidad_Academica {e}")


if __name__ == "__main__":
    inicio = time.time()
    with next(get_db()) as db:
        resultado = get_titulados(
            db=db,
            unidad_academica='ESIME Zacatenco',
            periodo='2025-2026/2',
            nivel='Posgrado',
            usuario='eesquivelo1300',
            host='Test'
        )
        print(len(resultado))
    
    #resultado = ejercicioDOS(18446744073709551629,  1, 3, (3942083613116040372 , 17718673197222366791 , 1), ( 13261599668560413002 , 18256791380151134939 , 1))
    print(resultado)
    fin = time.time()
    print(f"Tiempo de ejecución: {fin - inicio:.4f} segundos")
