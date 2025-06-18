FROM python:3.12-slim

# Set environment variables to non-interactive to suppress prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies and security updates
RUN apt-get update && \
    apt-get dist-upgrade -y && \
    apt-get install -y --no-install-recommends \
        libmagic1 \
        cups-client \
        poppler-utils \
        unoconv \
        libreoffice-core \
        libreoffice-writer \
        ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy script into the image
COPY print_email.py .

# Run the script
CMD ["python3", "print_email.py"]
