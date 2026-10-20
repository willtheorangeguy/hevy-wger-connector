FROM python:3.12.13-alpine
WORKDIR /app
COPY pyproject.toml ./
COPY README.md LICENSE ./
COPY requirements.lock ./
COPY src ./src
RUN pip install --no-cache-dir -r requirements.lock && pip install --no-cache-dir --no-deps . && adduser -D -u 10001 connector && mkdir /data && chown connector /data
USER connector
ENV DATA_DIR=/data PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
VOLUME ["/data"]
ENTRYPOINT ["hevy-wger"]
CMD ["watch"]
