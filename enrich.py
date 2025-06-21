# enrich.py - Simple version
import subprocess
import json
from util import logger
from database import add_channel, get_channel_by_id, add_video


def get_ytdlp_info(url):
    """Get all needed info from yt-dlp in a single call."""
    try:
        # Get all the info we need in one call using newlines as separators
        format_str = "%(channel)s\n%(channel_id)s\n%(channel_url)s\n%(id)s\n%(title)s\n%(uploader)s/%(upload_date>%Y-%m-%d)s - %(title)s [%(id)s].%(ext)s"

        result = subprocess.run(
            ["./yt-dlp", "--print", format_str, url],
            capture_output=True,
            text=True,
            check=True,
            timeout=30
        )

        lines = result.stdout.strip().split('\n')
        if len(lines) < 6:
            logger.error(f"Unexpected output format from yt-dlp for {url}")
            return None

        return {
            "channel": lines[0],
            "channel_id": lines[1],
            "channel_url": lines[2],
            "video_id": lines[3],
            "title": lines[4],
            "expected_filename": lines[5]
        }

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout getting info for {url}")
        return None
    except subprocess.CalledProcessError as e:
        logger.error(f"yt-dlp failed for {url}: {e.stderr}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting info for {url}: {e}")
        return None


def get_ytdlp_metadata(url):
    """Get basic metadata using JSON output to determine type."""
    try:
        result = subprocess.run(
            ["./yt-dlp", "--flat-playlist", "-J", url],
            capture_output=True,
            text=True,
            check=True,
            timeout=30
        )

        return json.loads(result.stdout)
    except Exception as e:
        logger.error(f"Error getting metadata for {url}: {e}")
        return None


def determine_item_type(url):
    """Determine if URL is a video, playlist, or channel."""
    metadata = get_ytdlp_metadata(url)
    if not metadata:
        return "unknown"

    _type = metadata.get("_type")
    extractor = metadata.get("extractor")

    logger.info(f'Found type: {_type}, extractor: {extractor} for {url}')

    if not _type or _type == 'video':
        return "video"
    elif extractor == "youtube:playlist":
        return "playlist"
    elif extractor in ("youtube:channel", "youtube:user"):
        return "channel"
    else:
        return "unknown"


def enrich_item(item):
    """
    Enrich an item dict by determining type and adding channel info.
    Returns True if enrichment succeeded, False otherwise.
    """
    url = item["url"]
    logger.info(f'Starting enrichment for item: {url}')

    # First determine what type of item this is
    item_type = determine_item_type(url)
    item["type"] = item_type

    if item_type == "unknown":
        logger.error(f"Could not determine type for {url}")
        return False

    # Get all info in a single call
    info = get_ytdlp_info(url)
    if not info:
        logger.error(f"Could not get info for {url}")
        return False

    channel_name = info.get("channel", "Unknown Channel")
    channel_id = info.get("channel_id", "")

    item["channel"] = channel_name
    logger.info(f'Enriched item {url} with channel: {channel_name} ({channel_id})')

    # Add/update channel in database
    if channel_id:
        add_channel(channel_id, channel_name)

    # If it's a video, also add it to the videos table
    if item_type == "video":
        video_id = info.get("video_id", "")
        title = info.get("title", "Unknown Title")
        expected_filename = info.get("expected_filename", "")

        # Add video to database
        if video_id:
            add_video(video_id, title, channel_id, expected_filename)
            logger.info(f'Added video to database: {title} ({video_id})')

    elif item_type in ["playlist", "channel"]:
        # For playlists and channels, we could populate videos later
        logger.info(f'Identified {item_type}: {channel_name}')

    return True


def populate_videos_from_channel(channel_id):
    """
    Populate the videos table with all videos from a channel.
    This can be run separately to discover all videos in a channel.
    """
    channel = get_channel_by_id(channel_id)
    if not channel:
        logger.error(f"Channel not found: {channel_id}")
        return False

    # Use yt-dlp to get video info from the channel
    try:
        format_str = "%(id)s\n%(title)s\n%(uploader)s/%(upload_date>%Y-%m-%d)s - %(title)s [%(id)s].%(ext)s"

        result = subprocess.run([
            "./yt-dlp",
            "--flat-playlist",
            "--print", format_str,
            f"https://www.youtube.com/channel/{channel_id}/videos"
        ], capture_output=True, text=True, check=True, timeout=60)

        lines = result.stdout.strip().split('\n')

        # Process videos in groups of 3 lines (id, title, expected_filename)
        for i in range(0, len(lines), 3):
            if i + 2 < len(lines):
                video_id = lines[i].strip()
                title = lines[i + 1].strip()
                expected_filename = lines[i + 2].strip()

                if video_id and title:
                    add_video(video_id, title, channel_id, expected_filename)

        logger.info(f'Populated videos for channel: {channel["name"]}')
        return True

    except Exception as e:
        logger.error(f"Error populating videos for channel {channel_id}: {e}")
        return False