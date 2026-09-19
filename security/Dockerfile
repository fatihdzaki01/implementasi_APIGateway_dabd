FROM python:3.11-slim

WORKDIR /app

COPY security/requirements.txt ./security/requirements.txt
RUN pip install --no-cache-dir -r security/requirements.txt

COPY shared/ ./shared/
COPY security/ ./security/

ENV PYTHONPATH=/app

EXPOSE 8030

CMD ["uvicorn", "security.main:app", "--host", "0.0.0.0", "--port", "8030"]
