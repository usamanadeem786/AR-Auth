FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy poetry files
COPY pyproject.toml poetry.lock ./

# Install poetry
RUN pip install poetry

# Configure poetry to create virtualenv in project directory
RUN poetry config virtualenvs.create false

# Install dependencies
RUN poetry install --no-dev --no-interaction --no-ansi

# Copy application code
COPY . .

# Compile translations and build static files
RUN poetry run pybabel compile --domain=messages --directory=auth/locale
RUN npm install && npm run build

# Expose port
EXPOSE 8000

# Run the application
CMD ["poetry", "run", "uvicorn", "auth.app:app", "--host", "0.0.0.0", "--port", "8000"]
