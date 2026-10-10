# syntax=docker/dockerfile:1

# ---- toolchain: everything needed to build and test the C++ core ----
FROM ubuntu:24.04 AS toolchain
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake ninja-build git ca-certificates \
        nlohmann-json3-dev libgtest-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src

# ---- core: build and test fgsim ----
FROM toolchain AS core
COPY core /src/core
RUN cmake -S core -B /build -G Ninja -DCMAKE_BUILD_TYPE=Release \
    && cmake --build /build \
    && ctest --test-dir /build --output-on-failure -j 4

# ---- dev: toolchain + Python, for running the whole test suite ----
FROM toolchain AS dev
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv postgresql-client \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
COPY pyproject.toml README.md /src/
COPY fleetguard /src/fleetguard
RUN pip install --no-cache-dir -e "/src[dev]"
COPY --from=core /build/fgsim /usr/local/bin/fgsim
ENV FG_FGSIM=/usr/local/bin/fgsim

# ---- runtime: API and worker ----
FROM ubuntu:24.04 AS runtime
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
WORKDIR /app
COPY pyproject.toml README.md /app/
COPY fleetguard /app/fleetguard
RUN pip install --no-cache-dir /app
COPY builds /app/builds
COPY db /app/db
COPY --from=core /build/fgsim /usr/local/bin/fgsim
ENV FG_FGSIM=/usr/local/bin/fgsim \
    FG_BUILDS_DIR=/app/builds \
    FG_MIGRATIONS_DIR=/app/db/migrations \
    FG_RUNS_DIR=/data/runs
CMD ["fleetguard", "builds", "list"]
