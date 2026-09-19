FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY gateway/requirements.txt ./gateway/requirements.txt
RUN pip install --no-cache-dir -r gateway/requirements.txt

# Copy shared module (needed for schemas, validation, logging, etc.)
COPY shared/ ./shared/

# Copy security module (needed for auth_middleware, rate_limit_middleware)
COPY security/ ./security/

# Copy gateway code
COPY gateway/ ./gateway/

# Set PYTHONPATH so imports work
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]