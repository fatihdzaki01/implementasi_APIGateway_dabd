FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY gateway/requirements.txt ./gateway/requirements.txt
RUN pip install --no-cache-dir -r gateway/requirements.txt

# Copy shared module (needed for schemas, validation, logging, etc.)
COPY shared/ ./shared/

# Copy gateway code
COPY gateway/ ./gateway/

# Set PYTHONPATH so imports work: from gateway.xxx import ..., from shared.xxx import ...
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]