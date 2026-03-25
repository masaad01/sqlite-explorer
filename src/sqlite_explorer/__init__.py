"""SQLite database explorer with metadata display and table pagination."""

import argparse
import csv
import os
import re
import sqlite3
import sys
from typing import Optional


def parse_column_defs(schema: str) -> list[tuple[str, str, bool]]:
    """Parse column definitions from a CREATE TABLE statement."""
    match = re.search(r'\((.+)\)', schema, re.DOTALL)
    if not match:
        return []
    
    cols = []
    for line in match.group(1).split(','):
        line = line.strip()
        if line.upper().startswith('PRIMARY KEY') or line.upper().startswith('UNIQUE') or line.upper().startswith('CHECK') or line.upper().startswith('FOREIGN KEY'):
            continue
        col_match = re.match(r'(\w+)\s+(\w+(?:\([^)]+\))?)', line, re.IGNORECASE)
        if col_match:
            name, dtype = col_match.groups()
            is_pk = 'PRIMARY KEY' in line.upper()
            cols.append((name, dtype.upper(), is_pk))
    return cols


def get_table_info(conn: sqlite3.Connection, table: str) -> list[tuple]:
    """Get all data from a table with pagination."""
    cursor = conn.cursor()
    cursor.execute(f'SELECT * FROM "{table}"')
    return cursor.fetchall()


def get_table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    """Get column names for a table."""
    cursor = conn.cursor()
    cursor.execute(f'PRAGMA table_info("{table}")')
    return [row[1] for row in cursor.fetchall()]


def get_row_count(conn: sqlite3.Connection, table: str) -> int:
    """Get total row count for a table."""
    cursor = conn.cursor()
    cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
    return cursor.fetchall()[0][0]


def get_all_tables(conn: sqlite3.Connection) -> list[tuple[str, int]]:
    """Get all tables and their row counts."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    return [(t, get_row_count(conn, t)) for t in tables]


def get_all_views(conn: sqlite3.Connection) -> list[str]:
    """Get all views."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='view' ORDER BY name"
    )
    return [row[0] for row in cursor.fetchall()]


def get_schema_raw(conn: sqlite3.Connection) -> str:
    """Get full database schema as raw CREATE statements."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type, name"
    )
    lines = []
    for row in cursor.fetchall():
        if row[0]:
            lines.append(row[0])
    return '\n\n'.join(lines)


def parse_view_columns(sql: str) -> list[tuple[str, str]]:
    """Extract column names from a CREATE VIEW AS SELECT statement."""
    match = re.search(r'AS\s+SELECT\s+(.+?)\s+FROM', sql, re.IGNORECASE | re.DOTALL)
    if not match:
        return []
    select_part = match.group(1)
    cols = []
    for col in select_part.split(','):
        col = col.strip()
        if ' AS ' in col.upper():
            col = re.split(r'\s+AS\s+', col, flags=re.IGNORECASE)[1].strip()
        cols.append((col.split('.')[-1].strip(), 'TEXT'))
    return cols


def get_schema_info(conn: sqlite3.Connection) -> tuple[list[dict], list[dict]]:
    """Get schema info as structured data for tree display."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name, sql, type FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type, name"
    )
    
    tables = []
    views = []
    
    for name, sql, obj_type in cursor.fetchall():
        if obj_type == 'table':
            cols = parse_column_defs(sql)
            tables.append({'name': name, 'columns': cols, 'sql': sql})
        else:
            cols = parse_view_columns(sql)
            views.append({'name': name, 'columns': cols, 'sql': sql})
    
    return tables, views


def format_ascii_table(headers: list[str], rows: list[tuple], offsets: Optional[list[int]] = None) -> str:
    """Format data as ASCII table."""
    if not rows:
        return f"{' | '.join(headers)}\n{'-+-'.join(['-' * len(h) for h in headers])}"

    if offsets is None:
        offsets = list(range(len(headers)))

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, idx in enumerate(offsets):
            val = str(row[idx]) if idx < len(row) else ''
            col_widths[i] = max(col_widths[i], len(val))

    def format_row(values: list[str], widths: list[int]) -> str:
        return ' | '.join(v.ljust(w) for v, w in zip(values, widths))

    separator = '-+-'.join(['-' * w for w in col_widths])
    header_line = format_row(headers, col_widths)
    
    lines = [header_line, separator]
    for row in rows:
        values = [str(row[idx]) if idx < len(row) else '' for idx in offsets]
        lines.append(format_row(values, col_widths))
    
    return '\n'.join(lines)


def output_csv(headers: list[str], rows: list[tuple], offsets: Optional[list[int]] = None, file=sys.stdout):
    """Output data as CSV."""
    if offsets is None:
        offsets = list(range(len(headers)))
    
    filtered_headers = [headers[i] for i in offsets]
    writer = csv.writer(file)
    writer.writerow(filtered_headers)
    
    for row in rows:
        values = [str(row[i]) if i < len(row) else '' for i in offsets]
        writer.writerow(values)


def format_schema_tree(conn: sqlite3.Connection, db_path: str):
    """Show database metadata in tree format."""
    size = os.path.getsize(db_path)
    print(f"{db_path} ({size:,} bytes)\n")
    
    tables, views = get_schema_info(conn)
    
    for i, table in enumerate(tables):
        prefix = "" if i == 0 else "\n"
        row_count = get_row_count(conn, table['name'])
        n = len(table['columns'])
        plural = "" if n == 1 else "s"
        print(f"{prefix}{table['name']} ({row_count:,} row{'s' if row_count != 1 else ''}, {n} col{plural})")
        
        for j, (col_name, col_type, is_pk) in enumerate(table['columns']):
            if j == len(table['columns']) - 1:
                sep = "└──"
            else:
                sep = "├──"
            pk_suffix = " PRIMARY KEY" if is_pk else ""
            print(f"    {sep} {col_name} {col_type}{pk_suffix}")
    
    if views:
        start = "\n" if tables else ""
        print(f"{start}views:")
        for i, view in enumerate(views):
            prefix = "" if i == 0 else "\n"
            print(f"{prefix}{view['name']}")
            for j, (col_name, col_type) in enumerate(view['columns']):
                if j == len(view['columns']) - 1:
                    sep = "└──"
                else:
                    sep = "├──"
                print(f"    {sep} {col_name} {col_type}")


def show_metadata_raw(conn: sqlite3.Connection, db_path: str):
    """Show database schema as raw CREATE statements."""
    print(f"Database: {db_path}")
    print(f"Size: {os.path.getsize(db_path):,} bytes\n")
    
    schema = get_schema_raw(conn)
    if schema:
        print("Schema")
        print("──────")
        print(schema)


def explore_table(
    conn: sqlite3.Connection,
    table: str,
    offset: int,
    limit: int,
    cols: Optional[list[str]] = None,
    as_csv: bool = False
):
    """Explore a specific table with optional filtering and pagination."""
    all_cols = get_table_columns(conn, table)
    total_rows = get_row_count(conn, table)

    if cols:
        invalid = set(cols) - set(all_cols)
        if invalid:
            print(f"Error: Invalid columns: {', '.join(sorted(invalid))}", file=sys.stderr)
            print(f"Available columns: {', '.join(all_cols)}", file=sys.stderr)
            sys.exit(1)
        selected_cols = cols
    else:
        selected_cols = all_cols

    offsets = [all_cols.index(c) for c in selected_cols]

    cursor = conn.cursor()
    col_list = ', '.join(f'"{c}"' for c in selected_cols)
    query = f'SELECT {col_list} FROM "{table}" LIMIT ? OFFSET ?'
    cursor.execute(query, (limit, offset))
    rows = cursor.fetchall()

    print(f"Table: {table}")
    print(f"Total rows: {total_rows:,}")
    print(f"Showing: {offset} to {min(offset + len(rows), offset + limit)}")
    if cols:
        print(f"Columns: {', '.join(selected_cols)}")
    print()

    if as_csv:
        output_csv(all_cols, rows, offsets)
    else:
        print(format_ascii_table(selected_cols, rows))


def main():
    parser = argparse.ArgumentParser(
        description='Explore SQLite databases with metadata and pagination.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s db.sqlite                    # Show schema and tables
  %(prog)s db.sqlite --table users     # Browse users table
  %(prog)s db.sqlite -t users --limit 50 --offset 100
  %(prog)s db.sqlite -t users --cols id,name,email
  %(prog)s db.sqlite -t users --csv > users.csv
        '''
    )
    parser.add_argument('db', help='SQLite database file')
    parser.add_argument('-t', '--table', help='Table to explore')
    parser.add_argument('--offset', type=int, default=0, help='Starting row (default: 0)')
    parser.add_argument('--limit', type=int, default=100, help='Rows per page (default: 100)')
    parser.add_argument('--cols', help='Filter columns (comma-separated)')
    parser.add_argument('--csv', action='store_true', help='Output as CSV')
    parser.add_argument('--schema', action='store_true', help='Show raw CREATE statements')

    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"Error: Database file not found: {args.db}", file=sys.stderr)
        sys.exit(1)

    try:
        conn = sqlite3.connect(args.db)
    except sqlite3.Error as e:
        print(f"Error: Cannot open database: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        cols = [c.strip() for c in args.cols.split(',')] if args.cols else None

        if args.table:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (args.table,)
            )
            if not cursor.fetchone():
                print(f"Error: Table not found: {args.table}", file=sys.stderr)
                sys.exit(1)

            explore_table(conn, args.table, args.offset, args.limit, cols, args.csv)
        else:
            if args.schema:
                show_metadata_raw(conn, args.db)
            else:
                format_schema_tree(conn, args.db)
    finally:
        conn.close()
