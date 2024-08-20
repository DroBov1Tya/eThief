FROM python:3.11-slim

WORKDIR /usr/src/app

COPY . .

ENV EMAIL_USER=""
ENV PASSWORD=""
ENV IMAP_SERVER=""

CMD ["python", "./main.py"]