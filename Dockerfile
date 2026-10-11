FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip freeze > /app/runtime-versions.txt
COPY app.py agent.py cloud.py retrieval.py entrypoint.sh ./
COPY static/ static/
COPY knowledge/ knowledge/
COPY index/ index/
RUN test -s index/index.faiss && test -s index/manifest.json && chmod +x entrypoint.sh
ENV PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1
EXPOSE 8080
ENTRYPOINT ["/app/entrypoint.sh"]
