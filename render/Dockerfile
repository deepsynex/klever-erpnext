ARG ERPNEXT_VERSION=v16.31.1
FROM frappe/erpnext:${ERPNEXT_VERSION}

USER root

RUN apt-get update \
    && apt-get install --no-install-recommends -y supervisor \
    && rm -rf /var/lib/apt/lists/*

COPY supervisord.conf /etc/supervisor/conf.d/frappe.conf
COPY render-entrypoint.sh /usr/local/bin/render-entrypoint.sh
RUN chmod 755 /usr/local/bin/render-entrypoint.sh \
    && mkdir -p /var/log/supervisor \
    && chown -R frappe:frappe /var/log/supervisor /etc/supervisor

USER frappe
WORKDIR /home/frappe/frappe-bench

EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/render-entrypoint.sh"]
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/frappe.conf"]
