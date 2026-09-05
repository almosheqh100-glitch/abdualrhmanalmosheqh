FROM python:3.13-slim

# تثبيت ffmpeg (ضروري لدمج الفيديو والصوت بعد التحميل)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "telegram_downloader_bot.py"]
