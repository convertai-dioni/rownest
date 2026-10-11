"""Excerpt: a data grid that stays fast on big tables and safe on user input.

Two ideas:
1. Do not run count(*) on every page load. Use the planner's estimate for large
   tables, and an exact count only for small tables or when a filter is active.
2. Sort and filter in SQL, not after fetching. Column names are checked against the
   table's real columns, identifiers are quoted, and values are escaped.
"""
import json

GRID_OPS = {"eq", "ne", "contains", "gt", "lt", "gte", "lte", "empty", "nempty"}


def grid_sort(sort, valid_cols):
    """'col' asc, '-col' desc. Unknown column -> no sort, never an error."""
    if not sort:
        return None, False
    desc = sort.startswith("-")
    col = sort[1:] if desc else sort
    return (col, desc) if col in valid_cols else (None, False)


def grid_filters(filters, valid_cols):
    lit = lambda v: "'" + str("" if v is None else v).replace("'", "''") + "'"
    clauses = []
    for f in json.loads(filters or "[]"):
        col, op, v = f.get("col"), f.get("op"), f.get("val")
        if col not in valid_cols or op not in GRID_OPS:
            continue                                   # skip, do not error
        c = quote_ident(col)
        q = c + "::text"
        if op == "eq":
            clauses.append(f"{q} = {lit(v)}")
        elif op == "contains":
            clauses.append(f"{q} ILIKE '%' || {lit(v)} || '%'")
        elif op == "empty":
            clauses.append(f"({c} IS NULL OR {q}='')")
        # ... ne, gt, lt, gte, lte, nempty follow the same shape
    return clauses


def total_rows(schema, table, has_filter):
    if has_filter:
        return query(f"SELECT count(*) FROM {schema}.{table} WHERE ...")   # exact over same predicate
    est = query("""SELECT COALESCE(NULLIF(c.reltuples, -1)::bigint, s.n_live_tup)
                   FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                   LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
                   WHERE n.nspname = %s AND c.relname = %s""", (schema, table))
    if est is None or est < 50_000:                    # small table: exact is cheap
        return query(f"SELECT count(*) FROM {schema}.{table}")
    return est                                         # big table: planner estimate
