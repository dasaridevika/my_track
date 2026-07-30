FROM mcr.microsoft.com/playwright/python:v1.54.0-noble
WORKDIR /app
ENV PLAYWRIGHT_BROWSERS_PATH=/app/.bin/ms-playwright
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium
COPY . .
EXPOSE 8501
EXPOSE 8000
CMD ["bash", "start.sh"]

