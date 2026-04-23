
![logo](./docs/logo/logo.svg)

> Optimize your auto consumption to maximize the impact of your solar installation.

## Setup
This repository is a monorepos containing the whole project, including the following parts
1. The [`backend`](/backend/README.md) as a Python API with the FastAPI framework, managed with UV.
1. The [`frontend`](/frontend/README.md) as a VueJS 3 SPA, using Vite, Pinia and Vue Router. Styled with TailwindCSS. This is also a PWA that can installed to have a native feel and simple access via the start menu.
1. The [`proxy`](/proxy) is a simple reverse proxy using [Caddy](https://caddyserver.com/) to support HTTPS and subdomains.
1. The [`infra`](/infra) is a Docker Compose infrastucture to start the whole infrastucture easily. It includes a Postgres database for the backend as well.
1. The [`docs`](/docs) stores all our technical and project documentations.

## Visit online
Visit [photov.srd.rs](https://photov.srd.rs).

Visit the [API docs](https://api.photov.srd.rs/docs) of the backend.

## Develop locally
Frontend - see [README](/frontend/README.md). You need [PNPM](https://pnpm.io/) installed.
```sh
cd frontend
pnpm dev
```
Open [http://127.0.0.1:5173](http://127.0.0.1:5173)

Backend - see [README](/backend/README.md). You need [UV](https://docs.astral.sh/uv/) installed.
```sh
cd backend
uv run fastapi dev
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000)

## Deploy in production
1. Buy and deploy a VPS with Docker Compose. We used this [Ansible automations for Fedora](https://codeberg.org/samuelroland/vps) to do it.
1. Make sure to connect a domain to the VPS
1. Open ports 22, 80 and 433 in firewall on the dashboard of your VPS provider
1. Clone the repos, build the containers and configure `.env`
    ```sh
    git clone https://github.com/PI-E2EEDA/PhotoV
    cd PhotoV/infra
    docker compose build
    cp .env.example .env
    vi .env
    ```
- You can quickly generate random values for `DB_PWD` and a `AUTH_SERVER_SECRET` with openssl. Please generate different values for both variables.
    ```sh
    openssl rand -base64 64
    ```
- Finally launch the infrastucture
    ```sh
    docker compose up
    ```
    HTTPS certificates will be generated automatically. You will be able to access your `$DOMAIN` directly in your browser, with API server served on `api.$DOMAIN`.

## Test

- Hello World
