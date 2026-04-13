# One off task to run manually on the server to import the whole history of a SolarEdge installation
from app.db import get_database_url
from app.tasks.util import print_success, print_error, print_warning

if __name__ == "__main__":
    print_success("Run db migrations")
    print("docker compose exec db sh")
    print("uv run alembic upgrade head")
    print_success("Easy access to Postgres")
    print("docker compose exec db sh")
    print("psql " + get_database_url(False).replace("+psycopg", ""))
