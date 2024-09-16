FROM python:3.12.6-slim

ARG PORKBUN_DDNS_VERSION=0.0.0

COPY . /tmp/porkbun-ddns

RUN cd /tmp/porkbun-ddns \
    && mv ./Docker/entrypoint.py /entrypoint.py \
    && export VERSION=${PORKBUN_DDNS_VERSION} \
    && python setup.py install \
    && rm -rf /tmp/porkbun-ddns

CMD [ "python", "/entrypoint.py" ]
