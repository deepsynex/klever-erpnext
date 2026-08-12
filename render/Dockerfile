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

COPY supervisord.conf /etc/supervisor/conf.d/frappe.conf
COPY render-entrypoint.sh /usr/local/bin/render-entrypoint.sh
RUN chmod 755 /usr/local/bin/render-entrypoint.sh \
    && mkdir -p /var/log/supervisor \
    && chown -R frappe:frappe /var/log/supervisor /etc/supervisor

WORKDIR /home/frappe/frappe-bench

EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/render-entrypoint.sh"]
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/frappe.conf"]
