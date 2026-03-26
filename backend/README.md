# Backend

Read [API docs](https://api.photov.srd.rs/docs)

## Start dev server
```sh
uv run fastapi dev
```

## Manage database

We are using [alembic] to manage migrations in our project. You can learn using with [this short video](https://www.youtube.com/watch?v=zTSmvUVbk8M).

We defined our models inside `app/models.py`.

At the start of the project, we used this command to setup the alembic project, this generate us an `migrations` folder. We had to tweak a few changes in commit `5b55900`. We also generated the first revision after having defined the first version of the models.
```sh
uv run alembic init migrations
# a few tweaks in 5b55900, then
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

## Authentication

We are using [Fastapi Users](https://fastapi-users.github.io/fastapi-users/latest/) with the bearer token transport and database strategy. Tokens expire after 3 weeks for inactivity. We only enabled the provided routes for login/logout and register. Password reset, user verification are not needed for now.

User verification will need to be done manually in the database.

We use the environment variable `AUTH_SERVER_SECRET` to let it sign verification and password reset tokens.

## Initial manual DB setup

Register a first user, change the password if this is production.
```sh
set domain "photov.srd.rs" # your domain
set domain "localhost:8000" # in dev
curl -s -X POST \
    -H "Content-Type: application/json" \
    -d '{ "email": "photov@photov.srd.rs", "password": "demo" }' \
    http://$domain/auth/register

{"id":1,"email":"photov@photov.srd.rs","is_active":true,"is_superuser":false,"is_verified":false}⏎  
```

You can run that on the database to manually verify the user.
```sql
select * from users; -- to detect what is the ID
update "user"
set is_verified = true
where id = 1 -- change the ID here if needed !
```

You can now try to login and you'll get an `access_token`.
```sh
> curl -s -X POST -d "username=photov@photov.srd.rs&password=demo" http://$domain/auth/login

{"access_token":"dlerz67RQuvv35myyOjtfo5u2BmTu4jd7AJLL0hjWeY","token_type":"bearer"}⏎    
```


