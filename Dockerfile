FROM debian:bookworm

RUN echo ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true | debconf-set-selections

RUN sed -i '/^Components:/s/main/main non-free contrib/' /etc/apt/sources.list.d/debian.sources

RUN apt update -qq && \
    DEBIAN_FRONTEND=noninteractive apt install -y --no-install-recommends \
        python3 python3-pip python3-setuptools python3-venv \
        libfontconfig wkhtmltopdf xvfb libpq-dev ttf-mscorefonts-installer fonts-noto \
        libxcomposite1 libxdamage1 libxtst6 libnss3 libcups2 libxss1 libxrandr2 libasound2 \
        libpangocairo-1.0-0 libatk1.0-0 libatk-bridge2.0-0 libgtk-3-0 libx11-xcb1 \
	tzdata

COPY binaries/cpdf/cpdf /usr/local/bin/
RUN chmod +x /usr/local/bin/cpdf

RUN python3 -m venv /opt/translate/venv

COPY requirements.txt constraints.txt /opt/translate/
RUN /opt/translate/venv/bin/pip3 install -r /opt/translate/requirements.txt -c /opt/translate/constraints.txt

RUN /opt/translate/venv/bin/python3 -c 'import pyppeteer.command; pyppeteer.command.install()'

COPY trans/static/fonts/ /usr/local/share/fonts/

COPY docker-entrypoint.sh /root/docker-entrypoint.sh
RUN chmod +x /root/docker-entrypoint.sh

COPY . /opt/translate/app

WORKDIR /opt/translate/app
ENTRYPOINT ["/root/docker-entrypoint.sh"]
