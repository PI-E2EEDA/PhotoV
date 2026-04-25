# Backups container

This container is a simple script running on configurable interval, that backups the postgres database with `pg_dump`. It also allow to run restoration manually with an existing backup file with `psql`.

```sh
> bash ./backup.sh
Usage: ./backup.sh <command> [args]
Commands:
  backup
  restore <filename.sql>
```

When starting the Docker compose service, it will run the `backup` subcommand.

To run this manually, you can just run this

```sh
docker compose run --rm backups backup
```

Same idea of the restore
```sh
> docker compose run --rm backups restore
ERROR: no restore files given among the /backups
Listing files
2026-04-25T15:37:18.sql  2026-04-25T15:42:22.sql  2026-04-25T15:44:59.sql
2026-04-25T15:40:31.sql  2026-04-25T15:42:37.sql  2026-04-25T15:45:11.sql
2026-04-25T15:40:44.sql  2026-04-25T15:42:50.sql  2026-04-25T15:45:23.sql
2026-04-25T15:40:56.sql  2026-04-25T15:43:02.sql  2026-04-25T15:45:35.sql
2026-04-25T15:41:08.sql  2026-04-25T15:43:14.sql  2026-04-25T15:45:37.sql
2026-04-25T15:41:20.sql  2026-04-25T15:43:26.sql  2026-04-25T15:45:46.sql
2026-04-25T15:41:32.sql  2026-04-25T15:43:38.sql  2026-04-25T16:00:02.sql
2026-04-25T15:41:46.sql  2026-04-25T15:44:22.sql  2026-04-25T16:03:36.sql
2026-04-25T15:41:58.sql  2026-04-25T15:44:34.sql  backups-logs.txt
2026-04-25T15:42:10.sql  2026-04-25T15:44:46.sql

# Example on restoring the last file
docker compose run --rm backups restore 2026-04-25T16:03:36.sql
```
