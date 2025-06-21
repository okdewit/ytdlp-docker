from datetime import datetime
from pony.orm import *
from database.base import db
from util import logger


class Item(db.Entity):
    """Item entity representing a video, playlist, or channel URL."""
    _table_ = 'items'
    id = PrimaryKey(int, auto=True)
    url = Required(str, unique=True)
    item_type = Optional(str, column='type')  # video, playlist, or channel
    created_at = Required(datetime, default=lambda: datetime.now())
    updated_at = Required(datetime, default=lambda: datetime.now())


def _item_to_dict(item):
    """Convert an Item entity to a dictionary."""
    return {
        "url": item.url,
        "type": item.item_type or ""
    }


@db_session
def get_all_items():
    """Get all items from database."""
    return [_item_to_dict(item) for item in select(i for i in Item).order_by(desc(Item.created_at))]


@db_session
def add_item(item_data):
    """Add an item to the database."""
    try:
        Item(
            url=item_data["url"],
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
def get_item_by_url(url):
    """Get a specific item by URL."""
    item = Item.get(url=url)
    if item:
        return _item_to_dict(item)
    return None


@db_session
def update_item(item_data):
    """Update an item in the database."""
    try:
        item = Item.get(url=item_data["url"])
        if item:
            item.item_type = item_data.get("type", item.item_type)
            item.updated_at = datetime.now()
            return True
        return False
    except Exception as e:
        logger.error(f"Error updating item: {e}")
        return False


@db_session
def item_exists(url):
    """Check if an item exists by URL."""
    return Item.exists(url=url)