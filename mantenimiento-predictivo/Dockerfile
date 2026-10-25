FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/home/app \
    PORT=8501

RUN groupadd --system app && useradd --system --gid app --create-home app
WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt && python -m pip check
COPY --chown=app:app app.py ./app.py
COPY --chown=app:app examples/ ./examples/
USER app
EXPOSE 8501
CMD ["sh", "-c", "exec python -m streamlit run app.py --server.address=0.0.0.0 --server.port=${PORT:-8501} --server.headless=true --server.maxUploadSize=10 --browser.gatherUsageStats=false"]
