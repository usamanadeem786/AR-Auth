# Auth Service

A FastAPI-based authentication service with background task processing using Dramatiq.

## Prerequisites

- Python 3.12+
- Node.js (for frontend assets)
- Access to a PostgreSQL 14+ database
- Access to a Redis instance

## Local Development Setup

### 1. Set Up Environment Variables

Create a `.env` file in the project root with your database and Redis credentials:

```bash
# Example using remote services
DATABASE_URL=postgresql://username:password@your-db-host:5432/dbname
REDIS_URL=redis://username:password@your-redis-host:6379/0

# Example using local Docker services
# DATABASE_URL=postgresql://auth:authpassword@localhost:5432/auth
# REDIS_URL=redis://localhost:6379/0
```

### 2. Set Up Python Environment

```bash
# Install Poetry if not already installed
curl -sSL https://install.python-poetry.org | python3 -

# Install project dependencies
poetry install

# Activate virtual environment
poetry shell
```

### 3. Run Database Migrations

```bash
# Generate migrations (if needed)
alembic -c auth/alembic.ini revision --autogenerate -m "initial"

# Apply migrations
alembic -c auth/alembic.ini upgrade head
```

### 4. Compile Translations and Build Static Files

```bash
# Compile translations
poetry run pybabel compile --domain=messages --directory=auth/locale

# Install frontend dependencies and build
npm install
npm run build
```

### 5. Run the Application

```bash
# Start the FastAPI server
poetry run uvicorn auth.app:app --host 0.0.0.0 --port 8000 --reload

# In a separate terminal, start the worker
poetry run dramatiq auth.worker -p 1 -t 1 -f auth.scheduler:schedule
```

## Development with Docker (Database and Redis Only)

### 1. Start Database and Redis

```bash
# Start services
docker compose up -d db redis

# Verify services are running
docker compose ps
```

### 2. Follow Local Development Setup

Continue with steps 2-5 from the Local Development Setup section above, but use these environment variables in your `.env` file:

```bash
DATABASE_URL=postgresql://auth:authpassword@localhost:5432/auth
REDIS_URL=redis://localhost:6379/0
```

## Full Docker Setup

### 1. Build and Start All Services

```bash
# Build and start all services
docker compose -f .docker/docker-compose.yml up -d --build

# Verify all services are running
docker compose -f .docker/docker-compose.yml ps
```

### 2. Access the Services

- FastAPI Application: http://localhost:8000
- PostgreSQL: localhost:5432
- Redis: localhost:6379

### 3. View Logs

```bash
# View all service logs
docker compose -f .docker/docker-compose.yml logs -f

# View specific service logs
docker compose -f .docker/docker-compose.yml logs -f app
docker compose -f .docker/docker-compose.yml logs -f worker
```

### 4. Stop Services

```bash
# Stop all services
docker compose -f .docker/docker-compose.yml down

# Stop services and remove volumes
docker compose -f .docker/docker-compose.yml down -v
```

## Development Workflow with Docker

When using the full Docker setup, you can develop with hot-reloading:

1. The `auth` directory is mounted as a volume, so changes to Python files will automatically reload the application
2. The `js` and `styles` directories are mounted for frontend development
3. Database migrations can be run from within the container:

```bash
# Run migrations
docker compose -f .docker/docker-compose.yml exec app alembic -c auth/alembic.ini upgrade head
```

## Available Make Commands

```bash
# Run the application
make run

# Run the worker
make worker

# Run tests
make test

# Run linting
make lint

# Compile translations
make translations-compile

# Build static files
make static-build
```

## Project Structure

```
.
├── auth/               # Main application code
├── .docker/           # Docker configuration files
├── js/                # JavaScript source files
├── styles/            # CSS source files
├── tests/             # Test files
├── .env               # Environment variables
├── docker-compose.yml # Docker Compose configuration
├── Makefile          # Development commands
├── pyproject.toml    # Python dependencies
└── README.md         # This file
```
