FROM fedora:43 as frontendbuild
RUN dnf install -y git wget pnpm
WORKDIR /frontend
COPY . /frontend
RUN rm -rf node_modules
RUN pwd && ls && pnpm i
RUN pnpm build

# Take /frontend/web/dist as the final useful folder for the web interface
FROM caddy:2.8-alpine
# Copy static files to default location of Caddy (/srv)
COPY --from=frontendbuild /frontend/dist /srv
# Copy config file of Caddy
COPY deploy/Caddyfile /etc/caddy/Caddyfile

WORKDIR /srv
EXPOSE 80
