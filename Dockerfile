# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for CadQuery
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libgl-dev \
    libglu1-mesa \
    libglu1-mesa-dev \
    libxi6 \
    libxi-dev \
    libxmu6 \
    libxmu-dev \
    libxrender1 \
    libxrender-dev \
    libxext6 \
    libxext-dev \
    libglut3.12 \
    libglut-dev \
    mesa-common-dev \
    libgomp1 \
    libsm6 \
    libice6 \
    libx11-6 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Make start script executable
RUN chmod +x start.sh

# Expose port (Railway will set this via $PORT)
ENV PORT=8080
EXPOSE 8080

# Start command - use the startup script
CMD ["./start.sh"]
