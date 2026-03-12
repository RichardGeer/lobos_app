## Refresh DB schema snapshot

sudo -u postgres pg_dump -d lobos_db --schema-only > docs/currentDBschema.sql
./scripts/export_db_schema.sh
