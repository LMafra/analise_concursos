# Alternativa para quem não tem o uv: já vem com o Tesseract em português.
#   docker build -t gabarito-vivo .
#   docker run --rm -it --user "$(id -u):$(id -g)" -v "$PWD:/dados" gabarito-vivo
# A pasta montada em /dados é o projeto: provas/, analises/ e .gabarito-vivo/ ficam no host.
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
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev

ENV PATH=/opt/venv/bin:$PATH \
    GABARITO_VIVO_HOME=/dados/.gabarito-vivo-home \
    MPLCONFIGDIR=/tmp/matplotlib \
    XDG_CACHE_HOME=/tmp/cache

WORKDIR /dados
ENTRYPOINT ["gabarito-vivo"]
CMD ["--no-open"]
