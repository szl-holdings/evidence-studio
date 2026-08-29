# Evidence Studio — merge sink hologram. One writer. Not a flagship.
FROM mirror.gcr.io/library/python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=7860
COPY space/server.py ./server.py
COPY space/index.html ./index.html
EXPOSE 7860
CMD ["python", "-u", "server.py"]
