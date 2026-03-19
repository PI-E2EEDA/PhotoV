
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
TODO
