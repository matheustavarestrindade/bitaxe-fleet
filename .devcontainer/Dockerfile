FROM node:24.13.0-bookworm-slim@sha256:4660b1ca8b28d6d1906fd644abe34b2ed81d15434d26d845ef0aced307cf4b6f AS node

FROM python:3.14.2-slim-bookworm@sha256:e87711ef5c86aaeaa7031718a69db79d334d94c545c709583f651b8185870941

ENV PATH="/opt/venv/bin:${PATH}" \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VIRTUAL_ENV=/opt/venv

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules

RUN apt-get update \
    && apt-get install --no-install-recommends --yes git \
    && rm --recursive --force /var/lib/apt/lists/* \
    && ln --symbolic /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln --symbolic /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && ln --symbolic /usr/local/lib/node_modules/corepack/dist/corepack.js /usr/local/bin/corepack \
    && useradd --create-home --shell /bin/bash vscode \
    && python -m venv "${VIRTUAL_ENV}" \
    && printf '%s\n' 'export PATH="/opt/venv/bin:$PATH"' > /home/vscode/.bash_profile \
    && chown --recursive vscode:vscode /home/vscode "${VIRTUAL_ENV}"

USER vscode
WORKDIR /workspaces/bitaxe-fleet
