import os
from datetime import datetime
from pony.orm import *
from util import logger

# Database setup
db = Database()

# Default yt-dlp parameters
DEFAULT_PARAMETERS = '-f "bv[vcodec^=av01][height<=1080]+ba/bv[ext=mp4][height<=1080]+ba/b[height<=1080]" --merge-output-format mp4 -o "%(uploader)s/%(upload_date>%Y-%m-%d)s - %(title)s [%(id)s].%(ext)s" --write-subs --sub-langs "en.*" --download-archive data/downloaded.txt --sponsorblock-mark all --sponsorblock-remove sponsor --embed-metadata --embed-thumbnail --write-info-json --write-desktop-link --write-description --write-thumbnail --convert-thumbnail jpg -P "data"'

DATABASE_PATH = "config/app.db"


class Item(db.Entity):
    """Item entity representing a video, playlist, or channel."""
    _table_ = 'items'  # Explicitly set table name to match existing
    id = PrimaryKey(int, auto=True)  # Add explicit primary key to match existing schema
    url = Required(str, unique=True)
    title = Optional(str)
    description = Optional(str)
    duration = Optional(str)
    channel = Optional(str)
    item_type = Optional(str, column='type')  # Map to 'type' column
    created_at = Required(datetime, default=lambda: datetime.now())
    updated_at = Required(datetime, default=lambda: datetime.now())


class Config(db.Entity):
    """Config entity for storing key-value configuration pairs."""
    _table_ = 'config'  # Explicitly set table name to match existing
    key = PrimaryKey(str)
    value = Optional(str)
    updated_at = Required(datetime, default=lambda: datetime.now())


def init_database():
    """Initialize the database and create tables."""
    # Ensure config directory exists
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

    # Bind database
    db.bind('sqlite', DATABASE_PATH)

    # Check if database file exists
    if os.path.exists(DATABASE_PATH):
        logger.info("Existing database found, checking schema compatibility...")

        # For existing database, we need to check if the type column exists
        # and add it if it doesn't, before generating mapping
        import sqlite3
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

    # Set up default parameters if they don't exist
    with db_session:
        if not Config.exists(key='parameters'):
            Config(key='parameters', value=DEFAULT_PARAMETERS)
            logger.info(f"Database initialized with default parameters: {DEFAULT_PARAMETERS[:100]}...")


@db_session
def get_config():
    """Get configuration as a dictionary (for template compatibility)."""
    # Get parameters
    params_config = Config.get(key='parameters')
    parameters = params_config.value if params_config else ""

    # Get all items
    items = []
    for item in select(i for i in Item).order_by(desc(Item.created_at)):
        items.append({
            "url": item.url,
            "title": item.title or "",
            "description": item.description or "",
            "duration": item.duration or "",
            "channel": item.channel or "",
            "type": item.item_type or ""
        })

    return {
        "options": {"parameters": parameters},
        "items": items
    }


@db_session
def get_all_items():
    """Get all items from database."""
    items = []
    for item in select(i for i in Item).order_by(desc(Item.created_at)):
        items.append({
            "url": item.url,
            "title": item.title or "",
            "description": item.description or "",
            "duration": item.duration or "",
            "channel": item.channel or "",
            "type": item.item_type or ""
        })
    return items


@db_session
def add_item(item_data):
    """Add an item to the database."""
    try:
        Item(
            url=item_data["url"],
            title=item_data.get("title", ""),
            description=item_data.get("description", ""),
            duration=item_data.get("duration", ""),
            channel=item_data.get("channel", ""),
            item_type=item_data.get("type", "")
        )
        return True
    except Exception as e:
        logger.error(f"Error adding item: {e}")
        return False


@db_session
def remove_item(url):
    """Remove an item from the database."""
    try:
        item = Item.get(url=url)
        if item:
            item.delete()
            return True
        return False
    except Exception as e:
        logger.error(f"Error removing item: {e}")
        return False


@db_session
def get_parameters():
    """Get the current parameters from config."""
    config = Config.get(key='parameters')
    return config.value if config else ""


@db_session
def set_parameters(parameters):
    """Set parameters in the database."""
    try:
        config = Config.get(key='parameters')
        if config:
            config.value = parameters
            config.updated_at = datetime.now()
        else:
            Config(key='parameters', value=parameters)
        return True
    except Exception as e:
        logger.error(f"Error setting parameters: {e}")
        return False


@db_session
def get_item_by_url(url):
    """Get a specific item by URL."""
    item = Item.get(url=url)
    if item:
        return {
            "url": item.url,
            "title": item.title or "",
            "description": item.description or "",
            "duration": item.duration or "",
            "channel": item.channel or "",
            "type": item.item_type or ""
        }
    return None


@db_session
def update_item(item_data):
    """Update an item in the database."""
    try:
        item = Item.get(url=item_data["url"])
        if item:
            item.title = item_data.get("title", "")
            item.description = item_data.get("description", "")
            item.duration = item_data.get("duration", "")
            item.channel = item_data.get("channel", "")
            item.item_type = item_data.get("type", "")
            item.updated_at = datetime.now()
            return True
        return False
    except Exception as e:
        logger.error(f"Error updating item: {e}")
        return False


@db_session
def get_config_value(key, default=None):
    """Get a specific config value by key."""
    config = Config.get(key=key)
    return config.value if config else default


@db_session
def set_config_value(key, value):
    """Set a specific config value."""
    try:
        config = Config.get(key=key)
        if config:
            config.value = value
            config.updated_at = datetime.now()
        else:
            Config(key=key, value=value)
        return True
    except Exception as e:
        logger.error(f"Error setting config value: {e}")
        return False