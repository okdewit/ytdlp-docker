import os
import sqlite3
import json
from contextlib import contextmanager
from util import logger

DATABASE = "config/app.db"

# Default yt-dlp parameters
DEFAULT_PARAMETERS = '-f "bv[vcodec^=av01][height<=1080]+ba/bv[ext=mp4][height<=1080]+ba/b[height<=1080]" --merge-output-format mp4 -o "%(uploader)s/%(upload_date>%Y-%m-%d)s - %(title)s [%(id)s].%(ext)s" --write-subs --sub-langs "en.*" --download-archive data/downloaded.txt --sponsorblock-mark all --sponsorblock-remove sponsor --embed-metadata --embed-thumbnail --write-info-json --write-desktop-link --write-description --write-thumbnail --convert-thumbnail jpg -P "data"'


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # This allows accessing columns by name
    try:
        yield conn
    finally:
        conn.close()


def init_database():
    """Initialize the database with required tables."""
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)

    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()

        # Create items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT,
                description TEXT,
                duration TEXT,
                channel TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create config table for storing key-value pairs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Insert default parameters if not exists
        cursor.execute('''
            INSERT OR IGNORE INTO config (key, value) 
            VALUES ('parameters', ?)
        ''', (DEFAULT_PARAMETERS,))

        conn.commit()

        logger.info(f"Database initialized with default parameters: {DEFAULT_PARAMETERS[:100]}...")


def migrate_from_json():
    """Migrate existing JSON config to SQLite if it exists."""
    config_file = "config/config.json"

    if os.path.exists(config_file):
        try:
            with open(config_file) as f:
                config = json.load(f)

            with get_db() as conn:
                cursor = conn.cursor()

                # Migrate parameters
                parameters = config.get("options", {}).get("parameters", "")
                cursor.execute(
                    "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
                    ("parameters", parameters)
                )

                # Migrate items
                for item in config.get("items", []):
                    cursor.execute('''
                        INSERT OR IGNORE INTO items (url, title, description, duration, channel)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (
                        item["url"],
                        item.get("title", ""),
                        item.get("description", ""),
                        item.get("duration", ""),
                        item.get("channel", "")
                    ))

                conn.commit()

            # Backup the old config file
            backup_name = config_file + ".backup"
            os.rename(config_file, backup_name)
            logger.info(f"Migrated config from JSON to SQLite. Old config backed up as {backup_name}")

        except Exception as e:
            logger.error(f"Error migrating from JSON: {e}")


def get_config():
    """Get configuration as a dictionary (for template compatibility)."""
    with get_db() as conn:
        cursor = conn.cursor()

        # Get parameters
        cursor.execute("SELECT value FROM config WHERE key = 'parameters'")
        params_row = cursor.fetchone()
        parameters = params_row[0] if params_row else ""

        # Get all items
        cursor.execute('''
            SELECT url, title, description, duration, channel 
            FROM items 
            ORDER BY created_at DESC
        ''')
        items = []
        for row in cursor.fetchall():
            items.append({
                "url": row["url"],
                "title": row["title"] or "",
                "description": row["description"] or "",
                "duration": row["duration"] or "",
                "channel": row["channel"] or ""
            })

        return {
            "options": {"parameters": parameters},
            "items": items
        }


def get_all_items():
    """Get all items from database."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT url, title, description, duration, channel 
            FROM items 
            ORDER BY created_at DESC
        ''')
        items = []
        for row in cursor.fetchall():
            items.append({
                "url": row["url"],
                "title": row["title"] or "",
                "description": row["description"] or "",
                "duration": row["duration"] or "",
                "channel": row["channel"] or ""
            })
        return items


def add_item(item):
    """Add an item to the database."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO items (url, title, description, duration, channel)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            item["url"],
            item.get("title", ""),
            item.get("description", ""),
            item.get("duration", ""),
            item.get("channel", "")
        ))
        conn.commit()
        return cursor.rowcount > 0  # Returns True if item was inserted


def remove_item(url):
    """Remove an item from the database."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM items WHERE url = ?", (url,))
        conn.commit()
        return cursor.rowcount > 0  # Returns True if item was deleted


def get_parameters():
    """Get the current parameters from config."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM config WHERE key = 'parameters'")
        row = cursor.fetchone()
        return row[0] if row else ""


def set_parameters(parameters):
    """Set parameters in the database."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO config (key, value, updated_at) 
            VALUES ('parameters', ?, CURRENT_TIMESTAMP)
        ''', (parameters,))
        conn.commit()


def get_item_by_url(url):
    """Get a specific item by URL."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT url, title, description, duration, channel 
            FROM items 
            WHERE url = ?
        ''', (url,))
        row = cursor.fetchone()
        if row:
            return {
                "url": row["url"],
                "title": row["title"] or "",
                "description": row["description"] or "",
                "duration": row["duration"] or "",
                "channel": row["channel"] or ""
            }
        return None


def update_item(item):
    """Update an item in the database."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE items 
            SET title = ?, description = ?, duration = ?, channel = ?, updated_at = CURRENT_TIMESTAMP
            WHERE url = ?
        ''', (
            item.get("title", ""),
            item.get("description", ""),
            item.get("duration", ""),
            item.get("channel", ""),
            item["url"]
        ))
        conn.commit()


def get_config_value(key, default=None):
    """Get a specific config value by key."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM config WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else default


def set_config_value(key, value):
    """Set a specific config value."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO config (key, value, updated_at) 
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (key, value))
        conn.commit()