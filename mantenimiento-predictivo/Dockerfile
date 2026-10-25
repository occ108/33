FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/home/app \
    PORT=8501

RUN groupadd --system app && useradd --system --gid app --create-home app
WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN --mount=type=bind,target=/build-context \
    if [ -d /build-context/.wheels ]; then \
      python -m pip install --no-cache-dir --no-index --find-links=/build-context/.wheels -r requirements.txt; \
    else \
      python -m pip install --no-cache-dir -r requirements.txt; \
    fi && python -m pip check
COPY --chown=app:app app.py analysis.py exports.py catalog.py maintenance.py automotive.py data_contract.py i18n.py vehicle_analysis.py manufacturer.py manual_entry.py ./
COPY --chown=app:app examples/ ./examples/
COPY --chown=app:app resources/ ./resources/
COPY --chown=app:app catalog/ ./catalog/
COPY --chown=app:app locales/ ./locales/
COPY --chown=app:app assets/ ./assets/
COPY --chown=app:app .streamlit/config.toml ./.streamlit/config.toml
USER app
EXPOSE 8501
CMD ["sh", "-c", "exec python -m streamlit run app.py --server.address=0.0.0.0 --server.port=${PORT:-8501} --server.headless=true --server.maxUploadSize=10 --browser.gatherUsageStats=false"]
