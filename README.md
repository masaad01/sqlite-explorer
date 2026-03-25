# sqlite-explorer

A lightweight CLI tool for exploring SQLite databases.

## Features

- View database schema, tables, and row counts
- Browse table data with pagination (offset/limit)
- Filter columns
- Export to CSV

## Usage

```bash
# Show database metadata (schema, tables, row counts)
./sqlite_explorer.py database.db

# Browse a table (default: 100 rows starting at 0)
./sqlite_explorer.py database.db --table users

# Customize pagination
./sqlite_explorer.py database.db -t users --limit 50 --offset 100

# Filter columns
./sqlite_explorer.py database.db -t users --cols id,name,email

# Export to CSV
./sqlite_explorer.py database.db -t users --csv > users.csv
./sqlite_explorer.py database.db -t users --cols id,name --csv > filtered.csv
```

## Options

| Option | Description | Default |
|--------|-------------|---------|
| `db` | SQLite database file | required |
| `-t, --table` | Table to explore | None (metadata mode) |
| `--offset` | Starting row | 0 |
| `--limit` | Rows per page | 100 |
| `--cols` | Filter columns (comma-separated) | All |
| `--csv` | Output as CSV | False |

## Requirements

- Python 3.10+
- No external dependencies
