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
    """Muestra procedencia, licencia y límites de incorporación de cada fuente."""
    data = load_catalog()
    with st.expander('Biblioteca de datos industriales · Fuentes internacionales'):
        st.write('Consulta conjuntos para investigar maquinaria, sensores y mantenimiento. Las referencias no entrenan automáticamente el modelo ni se incorporan a tus archivos.')
        query = st.text_input('Buscar en la biblioteca', placeholder='Por ejemplo: presión, turbinas, rodamientos…')
        equipment = st.multiselect('Tipos de equipo', sorted({d['equipment'] for d in data['datasets']}))
        found = search_catalog(data, query, equipment)
        st.caption(f"{len(found)} fuentes de {len(data['datasets'])} · Revisión: {data['checked_at'][:10]}")
        for entry in found:
            st.markdown('**' + entry['name'] + '**')
            st.write(f"{entry['repository']} · {entry['equipment']} · {entry['data_kind']}")
            if entry['records'] is not None: st.caption(f"Registros indicados por la fuente: {entry['records']:,}")
            st.caption('Autoría: ' + entry.get('authors', entry['repository']))
            st.write(entry['description'])
            st.write('Adaptación necesaria: ' + entry['adaptation'])
            st.caption('Licencia: ' + entry['license'] + (f" · DOI: {entry['doi']}" if entry['doi'] else ''))
            st.link_button('Consultar fuente · ' + entry['id'], entry['url'])
            if entry.get('snapshot'):
                snapshot = entry['snapshot']
                st.caption(snapshot['note'])
                st.download_button('Descargar datos originales · ' + entry['id'],
                                   (CATALOG_PATH.parent / snapshot['file']).read_bytes(),
                                   snapshot['file'], 'text/csv')
            if not entry['license_verified']: st.warning('Confirma las condiciones antes de copiar o redistribuir estos datos.')
            st.divider()
        if not found: st.info('No hay coincidencias. Prueba con otro término o quita filtros.')
        st.download_button('Descargar catálogo y referencias (JSON)', CATALOG_PATH.read_bytes(), 'catalogo_datos_industriales.json', 'application/json')
        st.info('La importación requiere revisar unidades, fechas, permisos y significado de las etiquetas. No se inventan timestamps ni se mezclan bancos de ensayo con datos reales para afirmar precisión industrial.')
