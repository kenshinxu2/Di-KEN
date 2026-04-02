FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    fonts-dejavu \
    fonts-liberation \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Create fonts directory and download Oswald fonts from the correct NEW paths
RUN mkdir -p /fonts && \
    curl -L -o /fonts/Oswald-Bold.ttf "https://github.com/google/fonts/raw/main/ofl/oswald/static/Oswald-Bold.ttf" && \
    curl -L -o /fonts/Oswald-Regular.ttf "https://github.com/google/fonts/raw/main/ofl/oswald/static/Oswald-Regular.ttf"

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot code
COPY . .

CMD ["python", "bot.py"]
