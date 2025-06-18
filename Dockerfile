FROM python:3.10-slim

RUN apt-get update && \
    apt-get install -y cups-client libcups2 \
    libreoffice imagemagick poppler-utils && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY print_email.py .

CMD ["python3", "print_email.py"]

