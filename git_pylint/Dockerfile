FROM python:3.7-slim

RUN apt-get update
RUN apt-get install -y --no-install-recommends git
RUN apt-get purge -y --auto-remove
RUN rm -rf /var/lib/apt/lists/*

COPY pylint_git.py /usr/local/bin/pylint_git
COPY diffutils.py /usr/local/bin/
COPY reporter.py /usr/local/bin/
COPY sysutils.py /usr/local/bin/

COPY requirements.txt /root/
RUN pip install -r /root/requirements.txt

COPY pylint.conf /root/
