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
    filesize = Optional(int)  # File size in bytes (None if unknown)
    created_at = Required(datetime, default=lambda: datetime.now())

    # Relationships
    channel = Optional('Channel')


def _video_to_dict(video):
    """Convert a Video entity to a dictionary."""
    expected_filename = video.expected_filename or ""
    is_downloaded = check_video_downloaded(expected_filename)

    return {
        "id": video.id,
        "video_id": video.video_id,
        "title": video.title,
        "expected_filename": expected_filename,
        "filesize": video.filesize,
        "filesize_human": format_filesize(video.filesize) if video.filesize else None,
        "created_at": video.created_at.isoformat(),
        "channel_id": video.channel.channel_id if video.channel else None,
        "channel_name": video.channel.name if video.channel else None,
        "is_downloaded": is_downloaded
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
def get_channel_video_stats(channel_id):
    """Get aggregated video statistics for a channel."""
    from database.channels import Channel
    channel = Channel.get(channel_id=channel_id)
    if not channel:
        return None

    videos = list(select(v for v in Video if v.channel == channel))

    total_count = len(videos)
    downloaded_count = 0
    downloaded_size = 0
    total_size = 0

    for video in videos:
        expected_filename = video.expected_filename or ""
        is_downloaded = check_video_downloaded(expected_filename)

        if is_downloaded:
            downloaded_count += 1
            if video.filesize:
                downloaded_size += video.filesize

        if video.filesize:
            total_size += video.filesize

    return {
        "total_count": total_count,
        "downloaded_count": downloaded_count,
        "pending_count": total_count - downloaded_count,
        "downloaded_size": downloaded_size,
        "total_size": total_size,
        "downloaded_size_human": format_filesize(downloaded_size) if downloaded_size > 0 else "0 B",
        "total_size_human": format_filesize(total_size) if total_size > 0 else "0 B"
    }


@db_session
def add_video(video_id, title, channel_id=None, expected_filename=None, filesize=None):
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
                filesize=filesize,
                channel=channel
            )
            logger.info(f"Added video: {title} ({video_id}) - {format_filesize(filesize) if filesize else 'unknown size'}")
            return _video_to_dict(video)
        else:
            logger.info(f"Video already exists: {video_id}")
            return get_video_by_id(video_id)
    except Exception as e:
        logger.error(f"Error adding video: {e}")
        return None


@db_session
def update_video_filesize(video_id, filesize):
    """Update the filesize for an existing video."""
    try:
        video = Video.get(video_id=video_id)
        if video:
            video.filesize = filesize
            logger.info(f"Updated filesize for {video_id}: {format_filesize(filesize)}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error updating video filesize: {e}")
        return False


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


def format_filesize(size_bytes):
    """Convert bytes to human-readable format."""
    if size_bytes is None or size_bytes == 0:
        return "0 B"

    size_bytes = int(size_bytes)
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            if unit == 'B':
                return f"{size_bytes} {unit}"
            else:
                return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"