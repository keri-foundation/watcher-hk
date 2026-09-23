FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    build-essential \
    curl \
    libsodium-dev \
    libssl-dev \
    libffi-dev \
    procps \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    KERI_BASER_MAP_SIZE=1099511627776

WORKDIR /app/watcher-hk

# Install dependencies first so they're cached separately from source changes
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

COPY scripts/keri/cf/main/watcher-oobis.json ./scripts/keri/cf/main/watcher-oobis.json
COPY docker/scripts/ /app/watcher-hk/docker/scripts/
RUN chmod +x /app/watcher-hk/docker/scripts/*.sh

ENTRYPOINT ["/bin/bash"]
