FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV RG_DB=/data/rgtakip.sqlite3
VOLUME /data
EXPOSE 8000
CMD ["./start.sh"]
