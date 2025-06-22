import os
from datetime import datetime
from pony.orm import PrimaryKey, Required, Optional, db_session, desc, select
from database.base import db
from util import logger


class Video(db.Entity):
    """Video entity representing individual videos."""
    _table_ = 'videos'

    id = PrimaryKey(int, auto=True)
    video_id = Required(str, unique=True)  # YouTube video ID
    title = Required(str)
    expected_filename = Optional(str)  # Expected download filename
    created_at = Required(datetime, default=lambda: datetime.now())

    # Relationships
    channel = Optional('Channel')


def _video_to_dict(video):
    """Convert a Video entity to a dictionary."""
    expected_filename = video.expected_filename or ""
    return {
        "id": video.id,
        "video_id": video.video_id,
        "title": video.title,
        "expected_filename": expected_filename,
        "created_at": video.created_at.isoformat(),
        "channel_id": video.channel.channel_id if video.channel else None,
        "channel_name": video.channel.name if video.channel else None,
        "is_downloaded": check_video_downloaded(expected_filename)
    }


@db_session
def get_all_videos():
    """Get all videos from database."""
    return [_video_to_dict(video) for video in select(v for v in Video).order_by(desc(Video.created_at))]


@db_session
def get_videos_by_channel(channel_id):
    """Get all videos for a specific channel."""
    from database.channels import Channel
    channel = Channel.get(channel_id=channel_id)
    if channel:
        return [_video_to_dict(video) for video in
                select(v for v in Video if v.channel == channel).order_by(desc(Video.created_at))]
    return []


@db_session
def add_video(video_id, title, channel_id=None, expected_filename=None):
    """Add a video to the database."""
    try:
        if not video_exists(video_id):
            from database.channels import Channel

            # Get channel if provided
            channel = None
            if channel_id:
                channel = Channel.get(channel_id=channel_id)

            video = Video(
                video_id=video_id,
                title=title,
                expected_filename=expected_filename,
                channel=channel
            )
            logger.info(f"Added video: {title} ({video_id})")
            return _video_to_dict(video)
        else:
            logger.info(f"Video already exists: {video_id}")
            return get_video_by_id(video_id)
    except Exception as e:
        logger.error(f"Error adding video: {e}")
        return None


@db_session
def get_video_by_id(video_id):
    """Get a video by its YouTube video ID."""
    video = Video.get(video_id=video_id)
    return _video_to_dict(video) if video else None


@db_session
def video_exists(video_id):
    """Check if a video exists by video ID."""
    return Video.exists(video_id=video_id)

def check_video_downloaded(expected_filename):
    """Check if video file exists on disk"""
    if not expected_filename:
        return False
    full_path = os.path.join("data", expected_filename)
    return os.path.exists(full_path)