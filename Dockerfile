FROM python:3.8-alpine3.11

RUN addgroup -S obsdcommits && adduser -S obsdcommits -G obsdcommits
WORKDIR /home/obsdcommits
COPY ./requirements.txt /home/obsdcommits/requirements.txt

RUN  \
 apk add --no-cache rsync perl && \
 apk add --no-cache postgresql-libs && \
 apk add --no-cache --virtual .build-deps gcc musl-dev postgresql-dev && \
 pip install --no-cache-dir -r /home/obsdcommits/requirements.txt && \
 apk --purge del .build-deps

USER obsdcommits
COPY ./commits-to-mastodon.py /home/obsdcommits/
COPY ./createsecret.py /home/obsdcommits/
COPY ./parse-commits.pl /home/obsdcommits/

CMD ["python", "/home/obsdcommits/commits-to-mastodon.py"]
