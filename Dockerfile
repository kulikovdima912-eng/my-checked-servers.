FROM python:3.11-slim
RUN apt-get update && apt-get install -y curl unzip && rm -rf /var/lib/apt/lists/*
RUN curl -L -o xray.zip https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip && unzip xray.zip && mv xray /usr/local/bin/ && chmod +x /usr/local/bin/xray && rm xray.zip
RUN pip install requests[socks]
COPY checker.py /app/checker.py
WORKDIR /app
CMD ["python", "checker.py"]
