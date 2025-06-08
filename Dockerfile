FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    wget \
    vim \
    net-tools \
    iputils-ping \
    ffmpeg \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN pip install flask apscheduler
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o ./yt-dlp
RUN chmod a+rwx ./yt-dlp

CMD ["python", "app.py"]