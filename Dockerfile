# Imagem de produção do Controle_Locacao (FastAPI + Jinja2 + HTMX), para o Coolify.
# O CSS compilado (static/css/app.css) já vai versionado: a imagem não precisa do Tailwind.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=America/Sao_Paulo

WORKDIR /app

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin locacao

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=locacao:locacao src ./src
COPY --chown=locacao:locacao static ./static

USER locacao
EXPOSE 8000

# /saude não exige login nem toca o banco. A imagem slim não tem curl: a sonda usa o próprio Python.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/saude', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "--factory", "src.web.app:criar_app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers"]
