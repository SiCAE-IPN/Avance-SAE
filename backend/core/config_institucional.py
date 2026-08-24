"""
Configuración Institucional para Oficios y Acuses de Conclusión (IPN / SEP).

Este archivo permite actualizar fácilmente cada año las imágenes de las mujeres
(heroína superior y personaje conmemorativo inferior) y los aniversarios sin necesidad
de modificar código fuente ni plantillas.
"""

from pathlib import Path
from typing import Any, Dict, List

# Ruta base donde se encuentran las imágenes institucionales
LOGOS_INSTITUCIONALES_DIR = Path("frontend/static/logos/institucional")

CONFIGURACION_INSTITUCIONAL: Dict[str, Any] = {
    # =========================================================================
    # 1. IMÁGENES MODIFICABLES CADA AÑO
    # =========================================================================
    "anio_vigente": 2026,
    
    # Imagen de la heroína o motivo patrio del encabezado superior derecho
    # Archivo ubicado en: frontend/static/logos/institucional/
    "imagen_heroina_header": "heroina_bandera.png",
    
    # Imagen conmemorativa del pie de página inferior izquierdo
    # Archivo ubicado en: frontend/static/logos/institucional/
    "imagen_personaje_footer": "margarita_maza_2026.png",
    
    # =========================================================================
    # 2. LOGOTIPOS INSTITUCIONALES FIJOS (SEP / IPN)
    # =========================================================================
    "logo_sep_ipn": "logo_sep_ipn.png",
    
    # =========================================================================
    # 3. ANIVERSARIOS CONMEMORATIVOS DEL AÑO (Modificables cada año)
    # =========================================================================
    "aniversarios": [
        "90 Aniversario del Instituto Politécnico Nacional",
        '90 Aniversario del CECyT 2 "Miguel Bernard"',
        "30 Aniversario de la UPIITA",
        "50 Aniversario del CICIMAR",
    ],
    
    # =========================================================================
    # 4. DATOS DE CONTACTO Y UBICACIÓN OFICIAL (Pie de página)
    # =========================================================================
    "pie_pagina": {
        "texto_oficial": (
            "Edificio de la Coordinación General de Planeación e Información Institucional, 1er. Piso, "
            "Unidad Profesional “Adolfo López Mateos”, Av. Miguel Othón de Mendizábal s/n, esq. Miguel Bernard, "
            "Col. Residencial La Escalera, Alcaldía Gustavo A. Madero, C.P. 07738, Ciudad de México. "
            "Tel: (55) 57 29 60 00 ext. 51852 y 51849"
        ),
        "color_barra": "#750946",  # Guinda IPN oficial
    },
    
    # =========================================================================
    # 5. AUTORIDAD FIRMANTE
    # =========================================================================
    "firmante": {
        "nombre": "MTRO. ORLANDO DAVID PARADA VICENTE",
        "cargo": "COORDINADOR GENERAL DE PLANEACION E INFORMACION INSTITUCIONAL",
        "lema": '"La Tecnica al Servicio de la Patria"',
    },
    
    # =========================================================================
    # 6. TEXTO OFICIAL DE NOTIFICACIÓN DE CONCLUSIÓN
    # =========================================================================
    "texto_oficial": (
        'Con esta fecha, se notifica de la conclusión de la captura de la información requerida '
        'a traves del "Sistema de Captura y Análisis de la Estadística (SICAE)", para el Proceso de '
        'Estadística Básica Institucional, de la que se acusa de recibido con el número de folio '
        'asignado en este documento. A partir de este momento, la Dirección de Información, '
        'dará inicio a la revisión de su información.'
    ),
    "titulo_proceso": "PROCESO DE ESTADISTICA BASICA INSTITUCIONAL",
}


def get_configuracion_institucional() -> Dict[str, Any]:
    """Retorna una copia de la configuración institucional vigente."""
    return dict(CONFIGURACION_INSTITUCIONAL)
