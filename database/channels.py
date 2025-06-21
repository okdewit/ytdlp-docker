from datetime import datetime
from pony.orm import PrimaryKey, Required, Set, db_session, desc, select
from database.base import db
from util import logger


class Channel(db.Entity):
    """Channel entity representing a YouTube channel."""
    _table_ = 'channels'

    id = PrimaryKey(int, auto=True)
    channel_id = Required(str, unique=True)
    name = Required(str)
    created_at = Required(datetime, default=lambda: datetime.now())

    # Relationships
    videos = Set('Video')


def _channel_to_dict(channel):
    """Convert a Channel entity to a dictionary."""
    return {
        "id": channel.id,
        "channel_id": channel.channel_id,
        "name": channel.name,
        "created_at": channel.created_at.isoformat(),
        "video_count": len(channel.videos)
    }


@db_session
def get_all_channels():
    """Get all channels from database."""
    return [_channel_to_dict(channel) for channel in select(c for c in Channel).order_by(Channel.name)]


@db_session
def add_channel(channel_id, name):
    """Add a channel to the database."""
    try:
        if not channel_exists(channel_id):
            channel = Channel(channel_id=channel_id, name=name)
            logger.info(f"Added channel: {name} ({channel_id})")
            return _channel_to_dict(channel)
        else:
            logger.info(f"Channel already exists: {channel_id}")
            return get_channel_by_id(channel_id)
    except Exception as e:
        logger.error(f"Error adding channel: {e}")
        return None


@db_session
def get_channel_by_id(channel_id):
    """Get a channel by its YouTube channel ID."""
    channel = Channel.get(channel_id=channel_id)
    return _channel_to_dict(channel) if channel else None


@db_session
def channel_exists(channel_id):
    """Check if a channel exists by channel ID."""
    return Channel.exists(channel_id=channel_id)