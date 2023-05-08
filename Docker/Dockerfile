FROM python:3.11.3-slim

COPY . /tmp/porkbun-ddns

RUN cd /tmp/porkbun-ddns \
    && mv ./Docker/entrypoint.py /entrypoint.py \
    && python setup.py install
    #&& rm -rf /tmp/porkbun-ddns

CMD [ "python", "/entrypoint.py" ]
