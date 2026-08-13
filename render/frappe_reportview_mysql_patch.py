"""Build-time patch: make list-view count queries work on real MySQL.

frappe.desk.reportview.get_count() prefixes count queries with the
MariaDB-only "SET STATEMENT max_statement_time=1 FOR ..." syntax whenever
frappe.db.db_type == "mariadb". Frappe has no separate "mysql" db_type, so
this also fires when the site is actually backed by real MySQL, which does
not understand that syntax and raises a 1064 syntax error on nearly every
list view. This patch adds a fallback: if that specific syntax error occurs,
retry the same count query without the timeout clause.
"""

from pathlib import Path

TARGET = Path("/home/frappe/frappe-bench/apps/frappe/frappe/desk/reportview.py")

OLD = (
	"\ttry:\n"
	"\t\tcount = frappe.db.sql(timeout_clause + count_sql, count_params)[0][0]\n"
	"\texcept Exception as e:\n"
	"\t\tif frappe.db.is_statement_timeout(e):  # Skip fetching accurate count\n"
	"\t\t\tcount = None\n"
	"\t\telse:\n"
	"\t\t\traise\n"
)

NEW = (
	"\ttry:\n"
	"\t\tcount = frappe.db.sql(timeout_clause + count_sql, count_params)[0][0]\n"
	"\texcept Exception as e:\n"
	"\t\tif frappe.db.is_statement_timeout(e):  # Skip fetching accurate count\n"
	"\t\t\tcount = None\n"
	"\t\telif timeout_clause and getattr(e, \"args\", [None])[0] == 1064:\n"
	"\t\t\t# Real MySQL doesn't support \"SET STATEMENT ... FOR\"; retry without it.\n"
	"\t\t\tcount = frappe.db.sql(count_sql, count_params)[0][0]\n"
	"\t\telse:\n"
	"\t\t\traise\n"
)

src = TARGET.read_text()

if OLD not in src:
	if NEW in src:
		print("reportview.py already patched, skipping")
		raise SystemExit(0)
	raise SystemExit(
		"frappe_reportview_mysql_patch: get_count() body has changed upstream; "
		"update this patch to match the new source"
	)

TARGET.write_text(src.replace(OLD, NEW, 1))
print("Patched frappe/desk/reportview.py for real-MySQL compatibility")
