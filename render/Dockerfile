ARG ERPNEXT_VERSION=v16.31.1
FROM frappe/erpnext:${ERPNEXT_VERSION}

USER root

RUN apt-get update \
    && apt-get install --no-install-recommends -y supervisor \
    && rm -rf /var/lib/apt/lists/*

# Railway (and possibly other platforms) mount an empty volume over sites/ with no
# copy-on-first-mount seeding, unlike a native `docker volume`. Keep a pristine copy of
# the image's baked sites/ defaults (apps.txt, apps.json, common_site_config.json) so the
# entrypoint can restore whatever the mount hid.
RUN mkdir -p /opt/frappe-bench-sites-defaults \
    && cp -a /home/frappe/frappe-bench/sites/. /opt/frappe-bench-sites-defaults/

# frappe's sequence.py assumes MariaDB-native CREATE SEQUENCE/nextval()/SETVAL() support
# whenever db_type=mariadb, but that's also the db_type used for real MySQL (frappe has no
# separate "mysql" db_type). Real MySQL doesn't support that syntax at all, so this
# doctors sequence.py to emulate sequences with a plain table when the server it's
# actually talking to isn't MariaDB. See render/frappe_sequence_mysql_patch.py.
COPY frappe_sequence_mysql_patch.py /home/frappe/frappe-bench/apps/frappe/frappe/database/sequence.py

# frappe.desk.reportview.get_count() prefixes list-view count queries with the
# MariaDB-only "SET STATEMENT max_statement_time=1 FOR ..." syntax whenever
# db_type=mariadb - which, per the same db_type limitation above, also fires
# against real MySQL. Real MySQL rejects that syntax with a 1064 error on
# nearly every list view, so this patches in a fallback that retries the same
# count query without the timeout clause when that specific error occurs.
# See render/frappe_reportview_mysql_patch.py.
COPY frappe_reportview_mysql_patch.py /tmp/frappe_reportview_mysql_patch.py
RUN python3 /tmp/frappe_reportview_mysql_patch.py && rm /tmp/frappe_reportview_mysql_patch.py

# set_execution_timeout() runs "SET SESSION max_statement_time = N", another
# MariaDB-only feature that db_type=mariadb also enables against real MySQL,
# which has no such system variable at all (error 1193). Some call sites (e.g.
# get_open_count(), hit on every sidebar/list view load) don't guard this call,
# crashing the request. Patch it into a safe no-op on real MySQL.
# See render/frappe_execution_timeout_mysql_patch.py.
COPY frappe_execution_timeout_mysql_patch.py /tmp/frappe_execution_timeout_mysql_patch.py
RUN python3 /tmp/frappe_execution_timeout_mysql_patch.py && rm /tmp/frappe_execution_timeout_mysql_patch.py

COPY supervisord.conf /etc/supervisor/conf.d/frappe.conf
COPY render-entrypoint.sh /usr/local/bin/render-entrypoint.sh
RUN chmod 755 /usr/local/bin/render-entrypoint.sh \
    && mkdir -p /var/log/supervisor \
    && chown -R frappe:frappe /var/log/supervisor /etc/supervisor

WORKDIR /home/frappe/frappe-bench

EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/render-entrypoint.sh"]
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/frappe.conf"]
