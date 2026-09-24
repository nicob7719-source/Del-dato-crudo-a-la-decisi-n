"""Configuracion central del proyecto: rutas y fuentes de datos.

No repetir estas URLs en otros modulos; importar siempre desde aqui.
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DATA_INTERIM_DIR = PROJECT_ROOT / "data" / "interim"
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
DATA_EXTERNAL_DIR = PROJECT_ROOT / "data" / "external"

MANIFEST_PATH = DATA_RAW_DIR / "manifest.json"

# Fuentes oficiales de la Direccion General de Ordenacion del Juego (DGOJ).
# Cada URL devuelve el CSV mas reciente publicado bajo ese identificador de
# documento (el nombre real del fichero llega en el header Content-Disposition
# y se registra en el manifiesto, junto con el trimestre que declara).
SOURCES = {
    "ggr_turnover": (
        "https://www.ordenacionjuego.es/cmis/document/alfresco/"
        "b93e9c1c-8575-474c-b68f-f80be16c82e3"
    ),
    "deposits_withdrawals": (
        "https://www.ordenacionjuego.es/cmis/document/alfresco/"
        "848fc8ff-d373-48cb-bc67-723c0692d624"
    ),
    "accounts": (
        "https://www.ordenacionjuego.es/cmis/document/alfresco/"
        "24c6e62e-59f7-490f-9961-98d0969cf787"
    ),
    "marketing": (
        "https://www.ordenacionjuego.es/cmis/document/alfresco/"
        "98b91310-62d1-4710-9bef-8e6f1ceec007"
    ),
}

DATA_DICTIONARY_URL = (
    "https://www.ordenacionjuego.es/en/cmis/document/alfresco/"
    "cffba8a4-f70b-4125-89ff-0a4c912cb777"
)

REQUEST_TIMEOUT_SECONDS = 30
