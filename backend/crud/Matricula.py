
"""Este archivo contiene las funciones CRUD para el modelo Matricula y consultas específicas usando SP."""

from backend.database.models.Matricula import Matricula
from backend.database.models.CatPeriodo import CatPeriodo as Periodo
from backend.database.models.CatUnidadAcademica import CatUnidadAcademica as Unidad_Academica
from backend.database.models.CatNivel import CatNivel as Nivel
from backend.services.periodo_service import get_ultimo_periodo, get_periodo_activo

from sqlalchemy import select, text
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from typing import Dict, List, Any, Optional, Tuple


############################__________________FUNCIONES CREATE____________________________############################
def create_matricula(db: Session, matricula_data: Dict[str, Any]) -> Matricula:
    """Crear una nueva entrada de matrícula."""
    new_matricula = Matricula(**matricula_data)
    db.add(new_matricula)
    db.commit()
    db.refresh(new_matricula)
    return new_matricula


############################__________________FUNCIONES READ____________________________############################
def get_matricula_by_filters(
    db: Session,
    id_unidad_academica: Optional[int] = None,
    id_programa: Optional[int] = None,
    id_modalidad: Optional[int] = None,
    id_semestre: Optional[int] = None,
    id_turno: Optional[int] = None,
    id_nivel: Optional[int] = None,
) -> List[Matricula]:
    """Obtener registros de matricula aplicando filtros opcionales."""
    query = db.query(Matricula)
    
    if id_unidad_academica is not None:
        query = query.filter(Matricula.Id_Unidad_Academica == id_unidad_academica)
    if id_programa is not None:
        query = query.filter(Matricula.Id_Programa == id_programa)
    if id_modalidad is not None:
        query = query.filter(Matricula.Id_Modalidad == id_modalidad)
    if id_semestre is not None:
        query = query.filter(Matricula.Id_Semestre == id_semestre)
    if id_turno is not None:
        query = query.filter(Matricula.Id_Turno == id_turno)
    if id_nivel is not None:
        query = query.filter(Matricula.Id_Nivel == id_nivel)
        
    return query.all()


def get_distinct_programa_ids_by_unidad(db: Session, id_unidad_academica: int) -> List[int]:
    """Obtener IDs únicos de programas para una unidad académica específica."""
    result = db.query(Matricula.Id_Programa).filter(
        Matricula.Id_Unidad_Academica == id_unidad_academica
    ).distinct().all()
    return [p.Id_Programa for p in result]


def get_distinct_grupo_edad_ids_by_unidad_nivel(db: Session, id_unidad_academica: int, id_nivel: int) -> List[int]:
    """Obtener IDs únicos de grupos de edad para una unidad académica y nivel específicos."""
    result = db.query(Matricula.Id_Grupo_Edad).filter(
        Matricula.Id_Nivel == id_nivel,
        Matricula.Id_Unidad_Academica == id_unidad_academica
    ).distinct().all()
    return [g.Id_Grupo_Edad for g in result]


############################__________________STORED PROCEDURES____________________________############################
def safe_row_to_dict(row, cols=None) -> Dict[str, Any]:
    """Convertir fila de resultado de SP a diccionario de forma segura."""
    # Priorizar mapping API si existe
    try:
        if hasattr(row, '_mapping'):
            return dict(row._mapping)
    except Exception:
        pass
    try:
        if hasattr(row, '_asdict'):
            return row._asdict()
    except Exception:
        pass
    # Si es tupla/lista, usar cols para mapear
    try:
        if isinstance(row, (list, tuple)) and cols:
            return {cols[i]: row[i] for i in range(min(len(cols), len(row)))}
    except Exception:
        pass
    # Fallback: intentar dict(row)
    try:
        return dict(row)
    except Exception:
        # última opción: inspeccionar atributos públicos
        rd = {}
        for attr in dir(row):
            if not attr.startswith('_') and not callable(getattr(row, attr)):
                try:
                    rd[attr] = getattr(row, attr)
                except Exception:
                    continue
        return rd


def _normalizar_texto_nota(valor: Any) -> Optional[str]:
    if valor is None:
        return None
    texto = str(valor).strip()
    if not texto or texto.lower() in {'none', 'null'}:
        return None
    return texto


def _extraer_nota_rechazo_de_resultset(rows: List[Any], columns: Optional[List[str]] = None) -> Optional[str]:
    columnas_candidatas = {
        'nota',
        'nnota',
        'motivo',
        'motivo_rechazo',
        'nota_rechazo',
        'rechazo',
        'observacion',
        'observaciones',
        'comentario',
    }

    if not rows:
        return None

    if isinstance(rows[0], dict):
        for row in rows:
            for key, value in row.items():
                if key and str(key).strip().lower() in columnas_candidatas:
                    nota = _normalizar_texto_nota(value)
                    if nota:
                        return nota

    if columns and len(columns) == 1:
        return _normalizar_texto_nota(rows[0][0] if isinstance(rows[0], (list, tuple)) and rows[0] else rows[0])

    if rows and isinstance(rows[0], (list, tuple)) and columns:
        for index, column_name in enumerate(columns):
            if str(column_name).strip().lower() in columnas_candidatas and index < len(rows[0]):
                nota = _normalizar_texto_nota(rows[0][index])
                if nota:
                    return nota

    return None


import time

# Cache en memoria para resultados del SP de Matricula
# Estructura: cache_key -> (timestamp, (rows_list, columns, nota_rechazo))
_MATRICULA_SP_CACHE: Dict[str, Tuple[float, Tuple[List[Dict[str, Any]], List[str], Optional[str]]]] = {}
_MATRICULA_SP_CACHE_TTL = 180  # 3 minutos de validez


def invalidate_matricula_sp_cache(unidad_sigla: Optional[str] = None, periodo: Optional[str] = None, nivel: Optional[str] = None):
    """
    Invalida el caché en memoria del SP de matrícula.
    Si no se especifican filtros, limpia todo el caché.
    """
    global _MATRICULA_SP_CACHE
    if unidad_sigla and periodo and nivel:
        cache_key = f"{str(unidad_sigla).strip().lower()}|{str(periodo).strip()}|{str(nivel).strip().lower()}"
        _MATRICULA_SP_CACHE.pop(cache_key, None)
    else:
        _MATRICULA_SP_CACHE.clear()


def execute_sp_consulta_matricula(
    db: Session,
    unidad_sigla: str,
    periodo: str,
    nivel: str,
    usuario: str = 'sistema',
    host: str = 'localhost',
    force_refresh: bool = False
) -> Tuple[List[Dict[str, Any]], List[str], Optional[str]]:
    """
    Ejecutar el SP SP_Consulta_Matricula_Unidad_Academica y devolver las filas normalizadas.
    Usa caché en memoria (TTL 3 min) para acelerar drásticamente exportaciones a PDF y consultas consecutivas.
    
    Args:
        db: Sesión de base de datos
        unidad_sigla: Sigla de la unidad académica (ej: 'ESE', 'ESCOM')
        periodo: Periodo académico (ej: '2025-2026/1')
        nivel: Nivel educativo (ej: 'Posgrado', 'Licenciatura')
        usuario: Nombre del usuario que ejecuta la consulta
        host: Host desde donde se realiza la petición
        force_refresh: Si es True, fuerza la consulta a la BD ignorando la caché
    
    Returns:
        Tuple[List[Dict], List[str], Optional[str]]: (filas como dicts, nombres de columnas, nota de rechazo)
    """
    cache_key = f"{str(unidad_sigla).strip().lower()}|{str(periodo).strip()}|{str(nivel).strip().lower()}"
    current_time = time.time()

    if not force_refresh and cache_key in _MATRICULA_SP_CACHE:
        cache_time, cached_result = _MATRICULA_SP_CACHE[cache_key]
        if (current_time - cache_time) < _MATRICULA_SP_CACHE_TTL:
            print(f"[matricula-sp] [CACHE] Retornando {len(cached_result[0])} registros desde CACHE en memoria para key='{cache_key}' (Exportacion ultrarrapida)")
            return cached_result

    try:
        # Usar conexión raw para manejar múltiples result sets
        connection = db.connection()
        
        # Ejecutar el SP con parámetros seguros (incluyendo @UUsuario y @HHost)
        sql = text("""
            EXEC SP_Consulta_Matricula_Unidad_Academica 
                @UUnidad_Academica = :unidad, 
                @PPeriodo = :periodo, 
                @NNivel = :nivel, 
                @UUsuario = :usuario, 
                @HHost = :host
        """)
        
        result = connection.execute(sql, {
            'unidad': unidad_sigla, 
            'periodo': periodo, 
            'nivel': nivel,
            'usuario': usuario, 
            'host': host
        })
        
        # PRIMER RESULT SET: Datos de matrícula
        rows = result.fetchall()

        # Obtener nombres de columnas si el driver los provee
        try:
            columns = list(result.keys())
        except Exception:
            columns = []

        # Normalizar filas a listas de dicts serializables
        rows_list = []
        for row in rows:
            try:
                row_dict = safe_row_to_dict(row, columns)

                # Convertir tipos no serializables a string cuando sea necesario
                for k, v in list(row_dict.items()):
                    if isinstance(v, (bytes, bytearray)):
                        try:
                            row_dict[k] = v.decode('utf-8', errors='ignore')
                        except Exception:
                            row_dict[k] = str(v)
                    elif not isinstance(v, (str, int, float, bool, type(None))):
                        row_dict[k] = str(v)

                rows_list.append(row_dict)
            except Exception:
                continue
        
        # SEGUNDO RESULT SET: Nota de rechazo (si existe)
        nota_rechazo = None
        try:
            # Primero intentar deducirla del propio set actual, por si el SP la expone como columna.
            nota_rechazo = _extraer_nota_rechazo_de_resultset(rows_list, columns)

            # Luego intentar leer sets adicionales usando nextset() en el cursor subyacente.
            if hasattr(result, 'cursor') and hasattr(result.cursor, 'nextset'):
                while result.cursor.nextset():
                    nota_rows = result.cursor.fetchall()
                    nota_columns = []
                    try:
                        if hasattr(result.cursor, 'description') and result.cursor.description:
                            nota_columns = [col[0] for col in result.cursor.description]
                    except Exception:
                        nota_columns = []

                    nota_encontrada = _extraer_nota_rechazo_de_resultset(nota_rows, nota_columns)
                    if nota_encontrada:
                        nota_rechazo = nota_encontrada
                        print(f"📋 Nota de rechazo capturada del SP: {nota_rechazo[:100]}...")
                        break
        except Exception as e:
            print(f"⚠️ No se pudo capturar segundo result set (Nota): {e}")

        # Guardar en caché para respuesta instantánea al exportar PDF
        _MATRICULA_SP_CACHE[cache_key] = (current_time, (rows_list, columns, nota_rechazo))
        return rows_list, columns, nota_rechazo

    except Exception as e:
        print(f"Error ejecutando SP: {e}")
        return [], [], None


def resolve_periodo_by_id_or_literal(db: Session, periodo_input: Optional[str], default: Optional[str] = None) -> str:
    """
    Resolver periodo por ID numérico o por literal. Si no se encuentra y no hay default,
    obtiene dinámicamente el último periodo. Si no existe ningún periodo, lanza excepción.
    
    Args:
        db: Sesión de base de datos
        periodo_input: ID como string ('9') o literal ('2025-2026/1')
        default: Periodo por defecto si no se encuentra (None = obtener dinámicamente)
        
    Returns:
        str: Periodo literal para usar en el SP
        
    Raises:
        ValueError: Si no hay ningún periodo configurado en el sistema
    """
    if not periodo_input:
        if default is None:
            _, periodo_literal = get_periodo_activo(db) or get_ultimo_periodo(db)
            if not periodo_literal:
                raise ValueError("No hay periodos configurados en el sistema. Por favor, cree al menos un periodo en Cat_Periodo.")
            return periodo_literal
        return default
        
    try:
        # Intentar interpretar como ID numérico
        periodo_id = int(periodo_input)
        periodo_obj = db.query(Periodo).filter(Periodo.Id_Periodo == periodo_id).first()
        if periodo_obj:
            return periodo_obj.Periodo
    except (ValueError, TypeError):
        # No es numérico, buscar por literal
        periodo_obj = db.query(Periodo).filter(Periodo.Periodo == periodo_input).first()
        if periodo_obj:
            return periodo_obj.Periodo
    
    # Si no se encuentra, usar default o obtener dinámicamente
    if default is None:
        _, periodo_literal = get_periodo_activo(db) or get_ultimo_periodo(db)
        if not periodo_literal:
            raise ValueError("No hay periodos configurados en el sistema. Por favor, cree al menos un periodo en Cat_Periodo.")
        default_periodo = periodo_literal
    else:
        default_periodo = default
    
    print(f"Aviso: Periodo '{periodo_input}' no encontrado, usando: {default_periodo}")
    return default_periodo


def get_unidad_and_nivel_info(db: Session, id_unidad: int, id_nivel: int) -> Tuple[Optional[str], Optional[str]]:
    """
    Obtener sigla de unidad académica y nombre de nivel por sus IDs.
    
    Returns:
        Tuple[Optional[str], Optional[str]]: (sigla_unidad, nombre_nivel)
    """
    unidad = db.query(Unidad_Academica).filter(Unidad_Academica.Id_Unidad_Academica == id_unidad).first()
    nivel = db.query(Nivel).filter(Nivel.Id_Nivel == id_nivel).first()
    
    unidad_sigla = unidad.Sigla if unidad else None
    nivel_nombre = nivel.Nivel if nivel else None
    
    return unidad_sigla, nivel_nombre
