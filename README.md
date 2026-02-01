# OpenTrace

A privacy-first missing persons tracing platform that aggregates and searches verified public data from official sources.

## Features

- **Verified Data Sources**: Integrates with NamUs, Interpol Yellow Notices, and The Charley Project
- **Privacy-Focused**: No personal data collection, all searches are anonymous
- **Real-time Updates**: Automated scraping with caching and rate limiting
- **RESTful API**: FastAPI-based with automatic OpenAPI documentation
- **Production Ready**: Docker containerized with Railway deployment

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL database
- Railway account (for deployment)

### Local Development

1. **Clone and setup:**
   ```bash
   git clone <repository-url>
   cd opentrace
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials
   ```

3. **Database setup:**
   ```bash
   # Create PostgreSQL database
   createdb opentrace_dev
   ```

4. **Run the application:**
   ```bash
   uvicorn api.main:app --reload
   ```

5. **Run tests:**
   ```bash
   python -m pytest tests/
   ```

## Deployment

### Railway (Recommended)

1. **Create Railway project:**
   ```bash
   railway login
   railway init
   ```

2. **Database setup:**
   - Add PostgreSQL service to your Railway project
   - Railway will automatically create `RAILWAY_DATABASE_URL` environment variable
   - **Important**: The app automatically converts Railway's `postgresql://` URLs to `postgresql+asyncpg://` for async compatibility

3. **Environment variables:**
   Set these in Railway dashboard:
   - `JWT_SECRET_KEY`: A secure random string (min 32 characters)
   - `DATABASE_URL`: Will be auto-set by Railway PostgreSQL service

4. **Deploy:**
   ```bash
   git push railway main
   ```

### Manual Docker Deployment

```bash
# Build and run
docker build -t opentrace .
docker run -p 8000:8000 --env-file .env opentrace
```

## API Documentation

Once running, visit `http://localhost:8000/docs` for interactive API documentation.

## Architecture

- **API Layer**: FastAPI with async endpoints
- **Database**: PostgreSQL with SQLAlchemy 2.0 async
- **Scrapers**: Respectful web scraping with caching
- **Auth**: JWT-based authentication for admin operations
- **Config**: Centralized environment variable management

## Data Sources

- **NamUs**: National Missing and Unidentified Persons System
- **Interpol Yellow Notices**: International wanted persons
- **The Charley Project**: Cold case missing persons

All data ingestion respects source terms of service and implements rate limiting.

## Security

- No user data collection
- All searches are anonymous
- Environment-based configuration (no hardcoded secrets)
- Non-root Docker containers
- JWT authentication for admin endpoints
- Input validation and sanitization

## Development

### Code Quality

```bash
# Run tests
python -m pytest tests/ --cov=app

# Validate environment
python scripts/validate_env.py

# Clean old logs
python scripts/clean_logs.py
```

### Project Structure

```
opentrace/
├── api/              # FastAPI routes and main app
├── auth/             # Authentication and security
├── core/             # Configuration and shared utilities
├── db/               # Database models and session
├── scrapers/         # Data source integrations
├── scripts/          # Utility scripts
└── tests/            # Test suite
```

## License

This project is dedicated to helping families find missing loved ones. All code is open source and available under the MIT License.