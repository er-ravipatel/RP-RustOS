FROM debian:bookworm-slim@sha256:99c0b25c46d0214d5a2091092e7908907dcaecd6a962cde0ac700acee222b6f3
RUN apt-get update && apt-get install -y --no-install-recommends build-essential flex bison bc libssl-dev libelf-dev gcc-aarch64-linux-gnu python3 ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY run.sh /usr/local/bin/rustos-dtb-repro
ENTRYPOINT ["/bin/sh", "/usr/local/bin/rustos-dtb-repro"]
