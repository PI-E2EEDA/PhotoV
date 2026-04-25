#!/bin/bash

LOGS_FILE="backups-logs.txt"

log() {
    echo "$@" | tee -a log "$BACKUPS_FOLDER"/$LOGS_FILE
}

checkenv() {
    if test -z "$BACKUPS_FOLDER"; then
        log BACKUPS_FOLDER variable is not defined ! You have to define a folder where the backups files will be generated.
        log IMPORTANT: you also have to mount this folder to avoid losing them on container restart.
        exit 1
    fi

    chmod 700 "$BACKUPS_FOLDER"

    if test -z "$BACKUPS_INTERVAL_MINUTES"; then
        log BACKUPS_INTERVAL_MINUTES variable is not defined ! You have to indicate how often the backups must run.
        exit 1
    fi

    if test -z "$POSTGRES_PASSWORD"; then
        log POSTGRES_PASSWORD variable is not defined !
        exit 1
    fi

    if test -z "$POSTGRES_USER"; then
        log POSTGRES_USER variable is not defined !
        exit 1
    fi

    if test -z "$DB_HOST"; then
        log DB_HOST variable is not defined !
        exit 1
    fi
}

# Password will be accessed by pg_dump and psql
# via PGPASSWORD https://stackoverflow.com/a/24158972
export PGPASSWORD="$POSTGRES_PASSWORD"

restore() {
    checkenv
    restore_file="$1"
    if test -z "$restore_file"; then
        log ERROR: no restore files given among the "$BACKUPS_FOLDER"
        echo Listing files
        ls "$BACKUPS_FOLDER"
        return 2
    fi

    if ! test -f "$BACKUPS_FOLDER/$restore_file"; then
        log "ERROR: file $restore_file doesn't exist !"
        return 2
    fi
    log Starting database backup at "$now"...
    timeout 120 psql -h "$DB_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" <"$BACKUPS_FOLDER/$restore_file"
    # We put a timeout to avoid blocking the whole script in case pg_dump runs infinitely
    log Backup is successful in file "$filename"
}

backup() {
    checkenv
    while true; do
        log "---" # empty line
        now="$(date --utc +%Y-%m-%dT%H:%M:%S)"
        filename="$now.sql"
        log Starting database backup at "$now"...
        # We put a timeout to avoid blocking the whole script in case pg_dump runs infinitely
        if timeout 120 pg_dump -h "db" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "$BACKUPS_FOLDER/$filename"; then
            log Backup is successful in file "$filename"
        else
            now="$(date --utc +%Y-%m-%dT%H:%M:%S)"
            log Backup failed at "$now" !
        fi

        log Starting to sleep "$BACKUPS_INTERVAL_MINUTES" minutes
        sleep "$BACKUPS_INTERVAL_MINUTES"m
    done
}

# Simple CLI definition
command="$1"
case "$command" in
backup)
    backup
    ;;

restore)
    if [[ $# -lt 1 ]]; then
        echo "Usage: $0 restore <filename.sql>"
        exit 1
    fi

    restore "$2"
    ;;

"" | -h | --help)
    echo "Usage: $0 <command> [args]"
    echo "Commands:"
    echo "  backup"
    echo "  restore <filename.sql>"
    ;;

*)
    echo "Unknown command: $command"
    exit 1
    ;;
esac
