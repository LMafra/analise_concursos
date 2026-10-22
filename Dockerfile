# Alternativa para quem não tem o uv: já vem com o Tesseract em português.
#   docker build -t concurso-analise .
#   docker run --rm -it --user "$(id -u):$(id -g)" -v "$PWD:/dados" concurso-analise
# A pasta montada em /dados é o projeto: provas/, analises/ e .concurso/ ficam no host.
FROM python:3.12-slim-trixie

COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /uvx /bin/

RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-por \
    && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev

ENV PATH=/opt/venv/bin:$PATH \
    CONCURSO_HOME=/dados/.concurso-home \
    MPLCONFIGDIR=/tmp/matplotlib \
    XDG_CACHE_HOME=/tmp/cache

WORKDIR /dados
ENTRYPOINT ["concurso-analise"]
CMD ["--no-open"]
