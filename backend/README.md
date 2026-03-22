# Backend

Read [API docs](https://api.photov.srd.rs/docs)

## Start dev server
```sh
POSTGRES_USER=photov POSTGRES_DB=photov POSTGRES_PASSWORD=demo uv run fastapi dev
```

## Manage database

We are using [alembic] to manage migrations in our project. You can learn using with [this short video](https://www.youtube.com/watch?v=zTSmvUVbk8M).

We defined our models inside `app/models.py`.

At the start of the project, we used this command to setup the alembic project, this generate us an `migrations` folder. We also generated the first revision after having defined the first version of the models.
```sh
uv run alembic init migrations
uv run alembic revision --autogenerate -m "Initial migration"
```

Now to generate the code to migrate the database from latest database revision, with a given title.
```sh
uv run alembic revision --autogenerate -m "Change this field"
```
You can know inspect the content of `migrations/versions` to see the new file.

To apply migrations up to the latest defined revisions
```sh
uv run alembic upgrade head
```
