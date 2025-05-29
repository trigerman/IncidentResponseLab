FROM debian:bullseye-slim

RUN apt-get update && apt-get install -y hping3 iputils-ping python3

COPY attack_script.py /attack_script.py
COPY payloads.txt /payloads.txt
COPY test.py /test.py

CMD ["python3", "/attack_script.py"]
