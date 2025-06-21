import os
import sqlite3
from pony.orm import Database, db_session
from util import logger

# Database setup
db = Database()

# Use absolute path to ensure we're in the right location
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_PATH = os.path.join(BASE_DIR, "config", "app.db")


def init_database():
    """Initialize the database and create tables."""
    logger.info(f"Initializing database at: {DATABASE_PATH}")
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Base directory: {BASE_DIR}")

    # Ensure config directory exists
    config_dir = os.path.dirname(DATABASE_PATH)
    logger.info(f"Config directory: {config_dir}")
    os.makedirs(config_dir, exist_ok=True)

    # Bind database
    db.bind('sqlite', DATABASE_PATH)

    # Import entities to register them with the database
    # This must be done after binding but before generate_mapping
    from database.items import Item
    from database.config import Config

    # Check if database file exists
    if os.path.exists(DATABASE_PATH):
        logger.info("Existing database found, checking schema compatibility...")

        # For existing database, check if the type column exists
        # and add it if it doesn't, before generating mapping
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Check if type column exists in items table
        cursor.execute("PRAGMA table_info(items)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'type' not in columns:
            logger.info("Adding 'type' column to items table")
            cursor.execute("ALTER TABLE items ADD COLUMN type TEXT")
            conn.commit()

        conn.close()

        # Now we can safely generate mapping
        db.generate_mapping(create_tables=False)
    else:
        # New database
        logger.info("Creating new database...")
        db.generate_mapping(create_tables=True)


def get_db():
    """Get the database instance."""
    return db


def get_database_path():
    """Get the database file path."""
    return DATABASE_PATH