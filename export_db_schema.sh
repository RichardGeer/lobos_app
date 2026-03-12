#!/bin/bash

DB_NAME="lobos_db"
OUTPUT_FILE="docs/currentDBtables.txt"

mkdir -p docs

echo "Exporting schema for database: $DB_NAME"
: > "$OUTPUT_FILE"

echo "==============================" >> "$OUTPUT_FILE"
echo "TABLE LIST" >> "$OUTPUT_FILE"
echo "==============================" >> "$OUTPUT_FILE"

sudo -u postgres psql -d "$DB_NAME" -c "\dt+" >> "$OUTPUT_FILE"

echo "" >> "$OUTPUT_FILE"
echo "==============================" >> "$OUTPUT_FILE"
echo "TABLE STRUCTURES" >> "$OUTPUT_FILE"
echo "==============================" >> "$OUTPUT_FILE"

TABLES=$(sudo -u postgres psql -d "$DB_NAME" -t -A -c \
"SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;")

while IFS= read -r TABLE
do
    [ -z "$TABLE" ] && continue

    echo "" >> "$OUTPUT_FILE"
    echo "--------------------------------------" >> "$OUTPUT_FILE"
    echo "TABLE: $TABLE" >> "$OUTPUT_FILE"
    echo "--------------------------------------" >> "$OUTPUT_FILE"

    sudo -u postgres psql -d "$DB_NAME" -c "\d+ $TABLE" >> "$OUTPUT_FILE"
done <<< "$TABLES"

echo "Done: $OUTPUT_FILE"
