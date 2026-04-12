
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

## SolarEdge integration
PhotoV is connecting to the SolarEdge API to access solar production, solar consumption and grid consumption, both in power and energy metrics. It first uses the SolarEdge API to retrieve the whole energy and power history at the start via a dedicated script. Second, it will also fetch the latest measures everyday at regular intervals.

### Relevant documentations
- [SolarEdge Monitoring API](https://knowledge-center.solaredge.com/sites/kc/files/se_monitoring_api.pdf): the most useful docs to understand the API routes, params and JSON structures.
- [User Roles and Permissions in SolarEdge ONE for C&I](https://knowledge-center.solaredge.com/sites/kc/files/se-user-roles-and-permissions-in-one-for-cni.pdf)
- [Python package `solaredge`](https://pypi.org/project/solaredge/). Not a tons of documentation but autocompletion or reading source code is enough.

#### How to generate an API token?
- Go login to the monitoring dashboard: [https://monitoring.solaredge.com](https://monitoring.solaredge.com)
- If you have access to the left tab named "Admin", this is easy, go under "Site Admin > Site Access > Access Control > API Access".
- If you don't have this tab (like [many](https://www.reddit.com/r/solar/comments/ateoku/solaredge_admin_account/) [people](https://www.reddit.com/r/SolarUK/comments/1llvn7c/solaredge_no_admin_panel_for_home_owners_no_api/) online), here is what we tried to help you figure it out:
    - At first, we had only 2 left tabs: Site Overview (all the interesting graphs) and Site Layout (to see the physical position and production of each panel)
    - We tried asking the company that installed our solar panels. They enabled the "complete access" our SolarEdge account. We received an automated email from SolarEdge indicating the change `Monitoring rights: DASHBOARD_AND_LAYOUT -> FULL_ACCESS` and `Device control access: NONE -> CONTROL`.
    - This has enabled 2 new left tabs: `Analysis` and `Reports` which were sadly completely useless for our needs...
    - We called again the installer company to ask if they could give us even more access rights. It seems they couldn't do much more...
    - What we finally did, as they have access to the Admin tab for our installation, is to ask them if they could generate an API key and send it to us. This is not ideal from a security standpoint as we cannot revoke the token without calling them. But the token has worked and we gave up continuing this boring process.
