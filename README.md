# sqlite-explorer

A lightweight CLI tool for exploring SQLite databases.

## Features

- View database schema, tables, and row counts
- Browse table data with pagination (offset/limit)
- Filter columns
- Export to CSV

## Installation

### From GitHub (requires pipx)

```bash
pipx install git+https://github.com/masaad01/sqlite-explorer.git
```

### From source

```bash
pip install git+https://github.com/masaad01/sqlite-explorer.git
```

### Development

```bash
pip install -e .
```

## Usage

```bash
# Show database metadata (schema, tables, row counts)
sqlite-explorer database.db

# Show raw CREATE statements
sqlite-explorer database.db --schema

# Browse a table (default: 100 rows starting at 0)
sqlite-explorer database.db --table users

# Customize pagination
sqlite-explorer database.db -t users --limit 50 --offset 100

# Filter columns
sqlite-explorer database.db -t users --cols id,name,email

# Export to CSV
sqlite-explorer database.db -t users --csv > users.csv
sqlite-explorer database.db -t users --cols id,name --csv > filtered.csv
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
| `--schema` | Show raw CREATE statements | False |

## Requirements

- Python 3.10+
- No external dependencies
