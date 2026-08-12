from frappe import db, scrub

# NOTE:
# FOR MARIADB - using no cache - as during backup, if the sequence was used in anyform,
# it drops the cache and uses the next non cached value in setval query and
# puts that in the backup file, which will start the counter
# from that value when inserting any new record in the doctype.
# By default the cache is 1000 which will mess up the sequence when
# using the system after a restore.
#
# Another case could be if the cached values expire then also there is a chance of
# the cache being skipped.
#
# FOR POSTGRES - The sequence cache for postgres is per connection.
# Since we're opening and closing connections for every request this results in skipping the cache
# to the next non-cached value hence not using cache in postgres.
# ref: https://stackoverflow.com/questions/21356375/postgres-9-0-4-sequence-skipping-numbers
SEQUENCE_CACHE = 0

# frappe's db_type is only ever "mariadb" / "postgres" / "sqlite" - there is no distinct
# "mysql" db_type, even when the server behind db_type=mariadb is actually vanilla MySQL.
# Real MySQL has no CREATE SEQUENCE / nextval() / SETVAL() support (that's MariaDB-only),
# so when db_type=mariadb but the server isn't actually MariaDB, emulate sequences with a
# plain table instead of native sequence objects.
_is_real_mysql_cache = None


def _is_real_mysql() -> bool:
	global _is_real_mysql_cache
	if _is_real_mysql_cache is None:
		version = db.sql("SELECT VERSION()")[0][0]
		_is_real_mysql_cache = "MariaDB" not in version
	return _is_real_mysql_cache


def _use_emulated_sequences() -> bool:
	return db.db_type == "mariadb" and _is_real_mysql()


def _ensure_emulated_sequence_table() -> None:
	db.sql_ddl(
		"""CREATE TABLE IF NOT EXISTS `__sequence_emulation` (
			sequence_name VARCHAR(140) NOT NULL PRIMARY KEY,
			current_value BIGINT NOT NULL
		) ENGINE=InnoDB"""
	)


def create_sequence(
	doctype_name: str,
	*,
	slug: str = "_id_seq",
	temporary: bool = False,
	check_not_exists: bool = False,
	cycle: bool = False,
	cache: int = SEQUENCE_CACHE,
	start_value: int = 0,
	increment_by: int = 0,
	min_value: int = 0,
	max_value: int = 0,
) -> str:
	sequence_name = scrub(doctype_name + slug)

	if _use_emulated_sequences():
		_ensure_emulated_sequence_table()
		initial_value = (start_value or 1) - 1
		if check_not_exists:
			db.sql(
				"INSERT IGNORE INTO `__sequence_emulation` (sequence_name, current_value) VALUES (%s, %s)",
				(sequence_name, initial_value),
			)
		else:
			db.sql(
				"REPLACE INTO `__sequence_emulation` (sequence_name, current_value) VALUES (%s, %s)",
				(sequence_name, initial_value),
			)
		return sequence_name

	query = "create sequence" if not temporary else "create temporary sequence"

	if check_not_exists:
		query += " if not exists"

	query += f" {sequence_name}"

	if increment_by:
		# default is 1
		query += f" increment by {increment_by}"

	if min_value:
		# default is 1
		query += f" minvalue {min_value}"

	if max_value:
		query += f" maxvalue {max_value}"

	if start_value:
		# default is 1
		query += f" start {start_value}"

	# in postgres, the default is cache 1 / no cache
	if cache:
		query += f" cache {cache}"
	elif db.db_type == "mariadb":
		query += " nocache"

	if not cycle:
		# in postgres, default is no cycle
		if db.db_type == "mariadb":
			query += " nocycle"
	else:
		query += " cycle"

	db.sql_ddl(query)

	return sequence_name


def get_next_val(doctype_name: str, slug: str = "_id_seq") -> int:
	sequence_name = scrub(f"{doctype_name}{slug}")

	if _use_emulated_sequences():
		_ensure_emulated_sequence_table()
		db.sql(
			"INSERT IGNORE INTO `__sequence_emulation` (sequence_name, current_value) VALUES (%s, 0)",
			(sequence_name,),
		)
		db.sql(
			"UPDATE `__sequence_emulation` SET current_value = LAST_INSERT_ID(current_value + 1) WHERE sequence_name = %s",
			(sequence_name,),
		)
		return db.sql("SELECT LAST_INSERT_ID()")[0][0]

	if db.db_type == "postgres":
		sequence_name = f"'\"{sequence_name}\"'"
	elif db.db_type == "mariadb":
		sequence_name = f"`{sequence_name}`"

	try:
		return db.sql(f"SELECT nextval({sequence_name})")[0][0]
	except IndexError:
		raise db.SequenceGeneratorLimitExceeded


def set_next_val(
	doctype_name: str, next_val: int, *, slug: str = "_id_seq", is_val_used: bool = False
) -> None:
	if _use_emulated_sequences():
		sequence_name = scrub(doctype_name + slug)
		value = next_val if is_val_used else next_val - 1
		_ensure_emulated_sequence_table()
		db.sql(
			"""INSERT INTO `__sequence_emulation` (sequence_name, current_value) VALUES (%s, %s)
			ON DUPLICATE KEY UPDATE current_value = %s""",
			(sequence_name, value, value),
		)
		return

	is_val_used = "false" if not is_val_used else "true"

	db.multisql(
		{
			"postgres": f"SELECT SETVAL('\"{scrub(doctype_name + slug)}\"', {next_val}, {is_val_used})",
			"mariadb": f"SELECT SETVAL(`{scrub(doctype_name + slug)}`, {next_val}, {is_val_used})",
		}
	)


def _get_existing_sequences() -> set[str]:
	if db.db_type == "postgres":
		rows = db.sql(
			"""SELECT sequence_name FROM information_schema.sequences
			WHERE sequence_schema = 'public'"""
		)
	elif _use_emulated_sequences():
		_ensure_emulated_sequence_table()
		rows = db.sql("SELECT sequence_name FROM `__sequence_emulation`")
	else:
		rows = db.sql(
			"""SELECT TABLE_NAME FROM information_schema.TABLES
			WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'SEQUENCE'"""
		)
	return {r[0] for r in rows}


def create_missing_sequences() -> list[str]:
	"""Recreate sequences for autoincrement doctypes whose sequence object is missing."""
	import frappe
	from frappe.query_builder.functions import Max

	if db.db_type == "sqlite":
		return []

	doctypes = frappe.get_all(
		"DocType",
		filters={"autoname": "autoincrement", "issingle": 0, "is_virtual": 0},
		pluck="name",
	)
	if not doctypes:
		return []

	existing = _get_existing_sequences()
	created = []

	for doctype in doctypes:
		if scrub(f"{doctype}_id_seq") in existing:
			continue

		# align past existing rows to avoid name collisions; empty tables fall
		# back to the default start (1), same as normal sequence creation
		table = frappe.qb.DocType(doctype)
		max_name = frappe.qb.from_(table).select(Max(table["name"])).run()[0][0]
		create_sequence(doctype, check_not_exists=True, start_value=int(max_name) + 1 if max_name else 0)
		created.append(doctype)

	return created
