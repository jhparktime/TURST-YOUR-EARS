FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home scorer
COPY server ./server
COPY web ./web
COPY scripts ./scripts
COPY examples ./examples
RUN mkdir /data && chown scorer:scorer /data
USER scorer
ENV DATA_DIR=/data
EXPOSE 8000
CMD ["uvicorn", "server.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
