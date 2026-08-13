"""Build-time patch: make set_execution_timeout() a no-op on real MySQL.

MariaDBConnectionUtil.set_execution_timeout() (defined identically in both
frappe/database/mariadb/mysqlclient.py and frappe/database/mariadb/database.py,
covering the MySQLdb and PyMySQL driver backends respectively) runs
"SET SESSION max_statement_time = N" whenever frappe.db.db_type == "mariadb".
Frappe has no separate "mysql" db_type (same root cause as the sequence.py and
reportview.py patches), so this also fires against real MySQL. Real MySQL has
no "max_statement_time" system variable at all - unlike the reportview.py
case, this isn't a syntax error but error 1193 "Unknown system variable".

frappe.database.database.Database.connect() already wraps its own call to
set_execution_timeout() in a try/except that just logs a warning, but
frappe.desk.notifications.get_open_count() (called on every doctype
sidebar/list view load to show linked-document counts) calls it directly
with no try/except, crashing the whole request on real MySQL. Rather than
patch every call site, make set_execution_timeout() itself swallow the
"unknown system variable" error so it's a safe no-op everywhere.
"""

from pathlib import Path

TARGETS = [
	Path("/home/frappe/frappe-bench/apps/frappe/frappe/database/mariadb/mysqlclient.py"),
	Path("/home/frappe/frappe-bench/apps/frappe/frappe/database/mariadb/database.py"),
]

OLD = (
	"\tdef set_execution_timeout(self, seconds: int):\n"
	'\t\tself.sql("set session max_statement_time = %s", int(seconds))\n'
)

NEW = (
	"\tdef set_execution_timeout(self, seconds: int):\n"
	"\t\ttry:\n"
	'\t\t\tself.sql("set session max_statement_time = %s", int(seconds))\n'
	"\t\texcept Exception as e:\n"
	'\t\t\t# Real MySQL has no "max_statement_time" system variable at all (unlike\n'
	"\t\t\t# MariaDB); treat that as a safe no-op instead of crashing the request.\n"
	'\t\t\tif getattr(e, "args", [None])[0] != 1193:\n'
	"\t\t\t\traise\n"
)

for target in TARGETS:
	src = target.read_text()

	if OLD not in src:
		if NEW in src:
			print(f"{target} already patched, skipping")
			continue
		raise SystemExit(
			f"frappe_execution_timeout_mysql_patch: set_execution_timeout() body has "
			f"changed upstream in {target}; update this patch to match the new source"
		)

	target.write_text(src.replace(OLD, NEW, 1))
	print(f"Patched {target} for real-MySQL compatibility")
