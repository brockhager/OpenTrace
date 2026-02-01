# scripts/validate_env.py
"""
Environment validation script for Opentrace.
Checks that all required environment variables are set before deployment.
"""
from core.config import settings


def main():
    """Validate environment configuration."""
    try:
        settings.validate()
        print("✅ All required environment variables are set.")
        print(f"   DATABASE_URL: {'*' * 10}... (PostgreSQL connection)")
        print(f"   JWT_SECRET_KEY: {'*' * len(settings.JWT_SECRET_KEY)} (length: {len(settings.JWT_SECRET_KEY)})")
        print(f"   LOG_RETENTION_DAYS: {settings.LOG_RETENTION_DAYS}")
        print(f"   RATE_LIMIT_WINDOW_HOURS: {settings.RATE_LIMIT_WINDOW_HOURS}")
        return True
    except ValueError as e:
        print(f"❌ Configuration validation failed: {e}")
        print("\nRequired environment variables:")
        print("  - DATABASE_URL (PostgreSQL connection string)")
        print("  - JWT_SECRET_KEY (at least 32 characters)")
        print("\nOptional environment variables:")
        print("  - LOG_RETENTION_DAYS (default: 30)")
        print("  - RATE_LIMIT_WINDOW_HOURS (default: 1)")
        print("  - MAX_SEARCH_RESULTS (default: 50)")
        print("  - PDF_PROCESSING_TIMEOUT (default: 30)")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)