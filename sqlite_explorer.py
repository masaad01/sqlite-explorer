#!/usr/bin/env python3
"""SQLite database explorer with metadata display and table pagination."""

import argparse
import csv
import os
import sqlite3
import sys
from typing import Optional


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


def get_schema(conn: sqlite3.Connection) -> str:
    """Get full database schema."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type, name"
    )
    lines = []
    for row in cursor.fetchall():
        if row[0]:
            lines.append(row[0])
    return '\n\n'.join(lines)


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


def show_metadata(conn: sqlite3.Connection, db_path: str):
    """Show database metadata: schema and tables."""
    print(f"Database: {db_path}")
    print(f"Size: {os.path.getsize(db_path):,} bytes\n")

    schema = get_schema(conn)
    if schema:
        print("=== Schema ===")
        print(schema)
        print()

    tables = get_all_tables(conn)
    if tables:
        print("=== Tables ===")
        table_data = [(name, count) for name, count in tables]
        print(format_ascii_table(['table', 'rows'], table_data))
        print()

    views = get_all_views(conn)
    if views:
        print("=== Views ===")
        for v in views:
            print(f"  {v}")


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
            show_metadata(conn, args.db)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
