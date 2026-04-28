FROM fedora:43
RUN dnf install -y postgresql && dnf clean all # just access pg_dump
COPY backup.sh .
RUN chmod +x backup.sh
ENTRYPOINT [ "./backup.sh" ]
