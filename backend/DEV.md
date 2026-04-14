# Dev Setup

Make sure you have [UV](https://docs.astral.sh/uv/) installed

## 1. Start PostgreSQL

In `infra/docker-compose.yml`, uncomment the ports for the `db` service:
```yaml
    ports:
      - "5432:5432"
```

Create the `.env` file:
```sh
cd infra
cp .env.example .env
```

The default password in `.env.example` is `photov`, which matches the backend's default. No need to change it for dev.

Start the database:
```sh
docker compose up db -d
```

**Note:** If you change the password in `.env` after the first launch, you must delete `infra/data/` and recreate the container. PostgreSQL only reads these env vars on first initialization.

```sh
docker compose down
rm -rf data/
docker compose up db -d
```

## 2. Run database migrations

```sh
cd backend
uv run alembic upgrade head
```

## 3. Start the backend

```sh
cd backend
export AUTH_SERVER_SECRET=dev-secret # deinfed here instead of in the .env in the infra folder
uv run fastapi dev
```

The API is available at http://localhost:8000. Docs at http://localhost:8000/docs.

## 4. Create a user account

Register:
```sh
curl -s -X POST \
    -H "Content-Type: application/json" \
    -d '{"email": "photov@photov.srd.rs", "password": "demo"}' \
    http://localhost:8000/auth/register
```

Verify the account manually in the database and init DB :

1. Connect to the database:
```sh
cd infra
docker compose exec db psql -U photov
```

2. Check the user ID:
```sql
SELECT id, email, is_verified FROM "user";
```

3. Verify the account:
```sql
UPDATE "user" SET is_verified = true WHERE id = 1;
```

4. Confirm:
```sql
SELECT id, email, is_verified FROM "user";
```

5. Init DB and exit :
```sql
INSERT INTO installation
VALUES (1, 'Home X', 'Le Moulin Neuf', 46.130400, 1.47356);

INSERT INTO userinstallationlink
VALUES (1, 1); -- the order is (user_id, installation_id)
\q
```

Login (to become your token):
```sh
curl -s -X POST \
    -d "username=photov@photov.srd.rs&password=demo" \
    http://localhost:8000/auth/login
```

## 5. Start the frontend (optional)

```sh
cd frontend
pnpm install
pnpm dev
```

Available at http://localhost:5173.