FROM python:3.15.0a5-slim

ARG PORKBUN_DDNS_VERSION=0.0.0

COPY . /tmp/porkbun-ddns

RUN cd /tmp/porkbun-ddns \
    && mv ./Docker/entrypoint.py /entrypoint.py \
    && export VERSION=${PORKBUN_DDNS_VERSION} \
    && pip install setuptools xdg-base-dirs \
    && python setup.py install \
    && rm -rf /tmp/porkbun-ddns

CMD [ "python", "/entrypoint.py" ]
