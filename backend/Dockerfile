# Utilisation de l'image officielle uv pour le build
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS build

# Installation des dépendances système (Tesseract + Poppler pour le PDF)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-fra \
    poppler-utils \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Optimisation UV : compilation bytecode
ENV UV_COMPILE_BYTECODE=1

# Copie des fichiers de dépendances
COPY pyproject.toml uv.lock ./

# Installation des dépendances (sans le projet lui-même pour mettre en cache la couche)
RUN uv sync --frozen --no-install-project --no-dev

# Copie du code source
COPY . .

# Installation finale
RUN uv sync --frozen --no-dev

# Port exposé
EXPOSE 8000

# Le dossier de stockage sera monté via un volume
ENV STORAGE_BASE_PATH=/app/storage

# Lancement
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
