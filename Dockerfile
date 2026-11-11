FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY profile.example.json sources.example.json ./
RUN useradd --create-home careerpilot && mkdir runtime && chown careerpilot runtime
USER careerpilot
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
