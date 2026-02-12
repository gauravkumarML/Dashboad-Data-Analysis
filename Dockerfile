# Use a lightweight Python base image
FROM python:3.11-slim

# Environment variables to optimize Python performance
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Working directory in the container
WORKDIR /app

# System dependency installation
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Dependency installation
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Application source code
COPY . .

# Expose Streamlit default port
EXPOSE 8501

# Healthcheck to ensure service availability
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# Startup command
ENTRYPOINT ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
