
FROM locustio/locust

COPY requirements.txt /
RUN set -ex \
    && pip install -r /requirements.txt

EXPOSE 8089/tcp
CMD locust -f /mnt/locust/locustfile.py  --config=/mnt/locust/locust.conf