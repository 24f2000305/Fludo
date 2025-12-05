#!/usr/bin/env bash
# Render Build Script for CadQuery Dependencies

echo "📦 Installing system dependencies for CadQuery..."

# Update package list
apt-get update -qq

# Install CadQuery system dependencies
apt-get install -y --no-install-recommends \
    build-essential \
    libgl1-mesa-dev \
    libglu1-mesa-dev \
    libxi-dev \
    libxmu-dev \
    freeglut3-dev \
    mesa-common-dev \
    libxrender1 \
    libxext6 \
    libsm6 \
    libice6

echo "✅ System dependencies installed"

# Install Python dependencies
echo "📦 Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Build complete!"
