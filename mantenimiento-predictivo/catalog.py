"""Catálogo local de referencias: no envía archivos ni consulta la red al cargarlo."""
import json
from pathlib import Path
import streamlit as st

CATALOG_PATH = Path(__file__).parent / 'resources' / 'catalog.json'


def load_catalog() -> dict:
    """Devuelve los metadatos de fuentes públicas revisadas, sin datos de usuarios."""
    return json.loads(CATALOG_PATH.read_text(encoding='utf-8'))


def search_catalog(catalog: dict, query: str = '', equipment: list[str] | None = None) -> list[dict]:
    """Filtra referencias por palabras y tipos de equipo; no busca en archivos subidos."""
    words = query.casefold().split()
    return [item for item in catalog['datasets']
            if (not equipment or item['equipment'] in equipment)
            and all(word in ' '.join(str(v) for v in item.values()).casefold() for word in words)]


def render_catalog() -> None:
    """Compatibility entry point using the new localized resource view."""
    from app import render_resources
    import streamlit as st
    render_resources(st.session_state.get('lang','es'))
