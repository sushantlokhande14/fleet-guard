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
    && ctest --test-dir /build --output-on-failure
