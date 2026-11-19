FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml requirements.lock ./
COPY backend ./backend
RUN pip install --no-cache-dir -r requirements.lock && pip install --no-deps . && useradd -m app && mkdir data && chown app data
USER app
EXPOSE 8000
CMD ["uvicorn", "casepilot.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
