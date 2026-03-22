
![logo](./docs/logo/logo.svg)

> Optimize your auto consumption to maximize the impact of your solar installation, without the pain of intuitive weather prediction.

## Setup
This repository is a monorepos containing the whole project, including the following parts
1. The [`backend`](/backend/README.md) as a Python API with the FastAPI framework, managed with UV.
1. The [`frontend`](/frontend/README.md) as a VueJS 3 SPA, using Vite, Pinia and Vue Router.
1. The [`proxy`](/proxy) is a simple reverse proxy using [Caddy](https://caddyserver.com/) to support HTTPS and subdomains.
1. The [`infra`](/infra) is a Docker Compose infrastucture to start the whole infrastucture easily. It includes a Postgres database for the backend as well.
1. The [`docs`](/docs) stores all our technical and project documentations.

## Visit online

Coming soon !

## Develop locally
TODO

## Deploy in production
1. Buy and deploy a VPS with Docker Compose. We used this [Ansible automations for Fedora](https://codeberg.org/samuelroland/vps) to do it.
1. Make sure to connect a domain to the VPS
1. Open ports 22, 80 and 433 in firewall on the dashboard of your VPS provider
1. Clone the repos, build the containers, configure `.env` and the start the infra !

```sh
git clone https://github.com/PI-E2EEDA/PhotoV
cd PhotoV/infra
docker compose build
cp .env.example .env
vi .env # configure domain and database password
```

You can quickly generate a database passwords with
```sh
openssl rand -base64 32
```

