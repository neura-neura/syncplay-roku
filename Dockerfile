FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bridge ./bridge
ENV SYNCPLAY_ROKU_DATA=/data
VOLUME /data
EXPOSE 8787
CMD ["python", "-m", "uvicorn", "bridge.app:app", "--host", "0.0.0.0", "--port", "8787", "--no-access-log", "--timeout-graceful-shutdown", "5"]
