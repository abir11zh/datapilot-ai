FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_MODE=cloud HOST=0.0.0.0 PORT=8501
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home --uid 10001 datapilot
COPY app.py ./
COPY frontend/ ./frontend/
COPY services/ ./services/
COPY pages/ ./pages/
COPY ml/ ./ml/
COPY prompts/ ./prompts/
RUN mkdir -p data/raw data/processed && chown -R datapilot:datapilot /app
USER datapilot
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8501')+'/api/health',timeout=3)"
CMD ["python", "app.py", "--server", "waitress"]
