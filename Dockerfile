FROM python:3.11-slim

# System deps + fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    fonts-dejavu \
    fonts-liberation \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Download Google Fonts (Oswald Bold & Regular)
RUN mkdir -p /fonts && \
    wget -q -O /fonts/Oswald-Bold.ttf \
      "https://github.com/google/fonts/raw/main/ofl/oswald/Oswald-Bold.ttf" && \
    wget -q -O /fonts/Oswald-Regular.ttf \
      "https://github.com/google/fonts/raw/main/ofl/oswald/Oswald-Regular.ttf"

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot.py .

CMD ["python", "bot.py"]
