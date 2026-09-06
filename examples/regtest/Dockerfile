FROM rust:1.93.1-bookworm@sha256:7c4ae649a84014c467d79319bbf17ce2632ae8b8be123ac2fb2ea5be46823f31 AS wallet
RUN apt-get update && apt-get install -y --no-install-recommends clang cmake protobuf-compiler python3 && rm -rf /var/lib/apt/lists/*
ENV RUSTUP_TOOLCHAIN=1.93.1 CARGO_BUILD_JOBS=4
WORKDIR /wallet
RUN curl -fLsS https://codeload.github.com/zingolabs/zingolib/tar.gz/9e897f8b2fc5f12a99604f2533164af62af7d3ac -o /tmp/wallet.tar.gz && \
    echo 'f94987a30ca23de557c3c5870c585f9bf5e2cc764ed0aedac3a54482877593d4  /tmp/wallet.tar.gz' | sha256sum -c - && \
    tar -xzf /tmp/wallet.tar.gz --strip-components=1 && rm /tmp/wallet.tar.gz
RUN cargo fetch --locked
COPY examples/regtest/patch_trust.py /tmp/patch_trust.py
RUN python3 /tmp/patch_trust.py && cargo build --offline --release -p zingo-cli && python3 /tmp/patch_trust.py --check-lock

FROM golang:1.26.8-bookworm@sha256:9fdc884aacc3bec89b20ffc69f4bb369c78210e3e4f600387b5128b12c199f81 AS indexer
WORKDIR /indexer
RUN curl -fLsS https://codeload.github.com/zcash/lightwalletd/tar.gz/d79cd1100575ff909d70e00d5514a4092df94934 -o /tmp/indexer.tar.gz && \
    echo 'accfc35cff6f0978da2aca911499052bfac4913a5117d2e7f16a4aa0f96b0e0e  /tmp/indexer.tar.gz' | sha256sum -c - && \
    tar -xzf /tmp/indexer.tar.gz --strip-components=1 && rm /tmp/indexer.tar.gz
RUN GOTOOLCHAIN=local CGO_ENABLED=0 go build -mod=readonly -o /lightwalletd .

FROM wallet AS devtool
RUN apt-get update && apt-get install -y --no-install-recommends clang cmake protobuf-compiler python3 pkg-config libssl-dev && rm -rf /var/lib/apt/lists/*
ENV RUSTUP_TOOLCHAIN=1.93.1 CARGO_BUILD_JOBS=4
WORKDIR /devtool
RUN curl -fLsS https://codeload.github.com/zcash/zcash-devtool/tar.gz/5a26ee854e634a4e88d1d79dab13f8fbb1eac6b8 -o /tmp/devtool.tar.gz && \
    echo '02ab2929c2d5bf6707411e583b16645cba14a86b2e2b6ec3acd3e0c3f13aefb3  /tmp/devtool.tar.gz' | sha256sum -c - && \
    tar -xzf /tmp/devtool.tar.gz --strip-components=1 && rm /tmp/devtool.tar.gz
COPY examples/regtest/patch_devtool.py /tmp/patch_devtool.py
RUN python3 /tmp/patch_devtool.py && cargo build --locked --release --features regtest_support

FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates openssl libssl3 libstdc++6 && rm -rf /var/lib/apt/lists/*
COPY --from=wallet /wallet/target/release/zingo-cli /usr/local/bin/zingo-cli
COPY --from=indexer /lightwalletd /usr/local/bin/lightwalletd
COPY --from=devtool /devtool/target/release/zcash-devtool /usr/local/bin/zcash-devtool
WORKDIR /opt/testkit
COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY pyproject.toml README.md LICENSE-MIT LICENSE-APACHE ./
COPY src ./src
RUN pip install --no-deps --no-build-isolation .
COPY examples/regtest /opt/lab
ENV PYTHONUNBUFFERED=1 ZCASH_LAB_CA=/lab/cert.pem
ENTRYPOINT ["python", "/opt/lab/lab.py"]
