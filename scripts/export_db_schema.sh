#!/bin/bash
cd "$(dirname "$0")"
DB_NAME="lobos_db"

DOCS_DIR="../docs"
SCHEMA_FILE="$DOCS_DIR/currentDBschema.sql"
TABLE_FILE="$DOCS_DIR/currentDBtables.txt"

mkdir -p "$DOCS_DIR"

echo "Exporting schema..."

sudo -u postgres pg_dump -d "$DB_NAME" --schema-only > "$SCHEMA_FILE"

echo "Exporting table structure..."

: > "$TABLE_FILE"

sudo -u postgres psql -d "$DB_NAME" -c "\dt+" >> "$TABLE_FILE"

TABLES=$(sudo -u postgres psql -d "$DB_NAME" -t -A -c \
"SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;")

for TABLE in $TABLES
do
    echo "" >> "$TABLE_FILE"
    echo "--------------------------------------" >> "$TABLE_FILE"
    echo "TABLE: $TABLE" >> "$TABLE_FILE"
    echo "--------------------------------------" >> "$TABLE_FILE"

    sudo -u postgres psql -d "$DB_NAME" -c "\d+ $TABLE" >> "$TABLE_FILE"
done

echo "Done."
echo "Schema file: $SCHEMA_FILE"
echo "Tables file: $TABLE_FILE"