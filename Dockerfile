# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
# CHANGED: Replaced 'libgl1-mesa-glx' with 'libgl1' for newer Debian compatibility
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the specific directories
COPY processing_pipeline /app/processing_pipeline
COPY proposal_generation_pipeline /app/proposal_generation_pipeline

# Set PYTHONPATH
ENV PYTHONPATH="${PYTHONPATH}:/app"