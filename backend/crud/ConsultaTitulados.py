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
        db.add_all(registros)
        db.commit()
        return len(registros)
    except Exception as e:
        db.rollback()
        raise e
    
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
