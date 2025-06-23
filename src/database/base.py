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

    # Ensure config directory exists
    config_dir = os.path.dirname(DATABASE_PATH)
    os.makedirs(config_dir, exist_ok=True)

    # Check if database file exists
    database_exists = os.path.exists(DATABASE_PATH)

    # If database doesn't exist, create an empty file for Pony ORM
    if not database_exists:
        logger.info("Creating new database file...")
        # Touch the file to create it
        with open(DATABASE_PATH, 'a'):
            pass

    # Bind database
    db.bind('sqlite', DATABASE_PATH)

    # Import all entities to register them with the database
    from database.config import Config
    from database.channels import Channel
    from database.videos import Video
    from database.subscriptions import Subscription

    if database_exists:
        logger.info("Existing database found, checking schema...")
        _migrate_database_schema()
        db.generate_mapping(create_tables=False)
    else:
        logger.info("Creating new database tables...")
        db.generate_mapping(create_tables=True)


def _migrate_database_schema():
    """Handle simple database schema setup."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        # Get list of existing tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [row[0] for row in cursor.fetchall()]

        if 'subscriptions' not in existing_tables:
            logger.info("Creating subscriptions table")
            cursor.execute('''
                CREATE TABLE subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL UNIQUE,
                    type TEXT,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    channel INTEGER REFERENCES channels(id)
                )
            ''')
            conn.commit()

        if 'channels' not in existing_tables:
            logger.info("Creating channels table")
            cursor.execute('''
                CREATE TABLE channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL
                )
            ''')
            conn.commit()

        if 'videos' not in existing_tables:
            logger.info("Creating videos table")
            cursor.execute('''
                CREATE TABLE videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    filesize INTEGER,
                    created_at TIMESTAMP NOT NULL,
                    channel INTEGER REFERENCES channels(id)
                )
            ''')
            conn.commit()

        logger.info("Database schema setup completed")

    except Exception as e:
        logger.error(f"Error during database setup: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def get_db():
    """Get the database instance."""
    return db


def get_database_path():
    """Get the database file path."""
    return DATABASE_PATH