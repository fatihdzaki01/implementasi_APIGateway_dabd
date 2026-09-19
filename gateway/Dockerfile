FROM python:3.11-slim

WORKDIR /app

# Install gateway dependencies
COPY gateway/requirements.txt ./gateway/requirements.txt
RUN pip install --no-cache-dir -r gateway/requirements.txt

# Install security dependencies (gateway import security.middleware at runtime)
COPY security/requirements.txt ./security/requirements.txt
RUN pip install --no-cache-dir -r security/requirements.txt

# Install shared dependencies
COPY shared/requirements.txt ./shared/requirements.txt
RUN pip install --no-cache-dir -r shared/requirements.txt

# Copy source code (context is repo root)
COPY shared/ ./shared/
COPY security/ ./security/
COPY gateway/ ./gateway/

# PYTHONPATH ke /app agar `import shared`, `import security`, `import gateway` semua resolve
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]