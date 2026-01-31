import os
import sys
import logging
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Configure logging to stdout
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s', stream=sys.stdout)
logger = logging.getLogger(__name__)

REQUIRED_ENV_VARS = [
    "DATABASE_URL",
    "GEMINI_API_KEY",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_PHONE_NUMBER",
    "ADMIN_PHONE_NUMBER",
]

OPTIONAL_ENV_VARS = [
    "INCOIS_API_KEY",
    "ALLOWED_ORIGINS",
    "MAPBOX_ACCESS_TOKEN", # Frontend mainly, but good to check
    "GROQ_API_KEY"
]

def check_env_vars():
    logger.info("--- Checking Environment Variables ---")
    all_present = True
    for var in REQUIRED_ENV_VARS:
        value = os.getenv(var)
        if not value:
            logger.error(f"❌ MISSING: {var}")
            all_present = False
        else:
            logger.info(f"✅ FOUND: {var} (Length: {len(value)})")
            
    for var in OPTIONAL_ENV_VARS:
        value = os.getenv(var)
        if not value:
            logger.warning(f"⚠️  MISSING OPTIONAL: {var}")
        else:
            logger.info(f"✅ FOUND OPTIONAL: {var} (Length: {len(value)})")
            
    return all_present

def check_database():
    logger.info("\n--- Checking Database Connection ---")
    try:
        from database import SessionLocal
        from sqlalchemy import text
        
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            logger.info("✅ Database connection successful!")
            return True
        except Exception as e:
            logger.error(f"❌ Database connection failed: {str(e)}")
            return False
        finally:
            db.close()
    except ImportError:
        logger.error("❌ Could not import database module. Is dependencies installed?")
        return False
    except Exception as e:
        logger.error(f"❌ Database check failed with unexpected error: {str(e)}")
        return False

def main():
    logger.info("Starting Deployment Check...")
    
    env_ok = check_env_vars()
    db_ok = check_database()
    
    logger.info("\n--- Summary ---")
    if env_ok and db_ok:
        logger.info("✅✅ SYSTEM CHECK PASSED! Service should start correctly.")
    else:
        logger.error("❌❌ SYSTEM CHECK FAILED! Please fix the errors above.")
        
    # Also print allowed origins explicitly for debug
    logger.info(f"\nALLOWED_ORIGINS: {os.getenv('ALLOWED_ORIGINS', 'Not Set (Default: http://localhost:8080)')}")

if __name__ == "__main__":
    main()
