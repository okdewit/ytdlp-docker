import os
import glob
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
    filesize = Optional(int)  # File size in bytes (None if unknown)
    created_at = Required(datetime, default=lambda: datetime.now())

    # Relationships
    channel = Optional('Channel')


def _video_to_dict(video):
    """Convert a Video entity to a dictionary."""
    is_downloaded = check_video_downloaded(video.video_id)

    return {
        "id": video.id,
        "video_id": video.video_id,
        "title": video.title,
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
        is_downloaded = check_video_downloaded(video.video_id)

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
def add_video(video_id, title, channel_id=None, filesize=None):
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


def check_video_downloaded(video_id: str, data_dir: str = "data") -> bool:
    """
    Check if video file exists on disk by scanning for files containing [video_id].

    Since yt-dlp always includes [video_id] in the filename, we can reliably
    detect downloaded videos without predicting the exact filename.

    Args:
        video_id: YouTube video ID (e.g., "YuojAtE8YCY")
        data_dir: Directory to search in (default: "data")

    Returns:
        True if video file exists, False otherwise
    """
    if not video_id:
        return False

    # Use a broader search first to find any files containing the video_id
    pattern = os.path.join(data_dir, "**", f"*{video_id}*")
    matches = glob.glob(pattern, recursive=True)

    # Filter matches to only include video files with [video_id] in the name
    video_extensions = ['.mp4', '.mkv', '.webm', '.avi', '.mov', '.flv', '.m4v']
    target_pattern = f"[{video_id}]"

    for match in matches:
        # Check if it's a video file and contains [video_id]
        if (any(match.lower().endswith(ext) for ext in video_extensions) and
            target_pattern in match):
            return True

    return False


def find_video_file_path(video_id: str, data_dir: str = "data"):
    """
    Find the actual file path for a downloaded video.

    Args:
        video_id: YouTube video ID
        data_dir: Directory to search in

    Returns:
        Relative path to the video file, or None if not found
    """
    if not video_id:
        return None

    # Use a broader search first to find any files containing the video_id
    pattern = os.path.join(data_dir, "**", f"*{video_id}*")
    matches = glob.glob(pattern, recursive=True)

    # Filter matches to only include video files with [video_id] in the name
    video_extensions = ['.mp4', '.mkv', '.webm', '.avi', '.mov', '.flv', '.m4v']
    target_pattern = f"[{video_id}]"

    for match in matches:
        # Check if it's a video file and contains [video_id]
        if (any(match.lower().endswith(ext) for ext in video_extensions) and
            target_pattern in match):
            return os.path.relpath(match)

    return None


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