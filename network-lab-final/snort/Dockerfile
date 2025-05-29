FROM ubuntu:20.04

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y snort python3 tcpdump net-tools

COPY flag_checker.py /flag_checker.py
COPY found /usr/local/bin/found
COPY motd /motd

RUN chmod +x /usr/local/bin/found
RUN echo "cat /motd" >> /etc/bash.bashrc

CMD ["bash"]
