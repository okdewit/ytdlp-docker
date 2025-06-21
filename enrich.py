# enrich.py - Updated for subscriptions
import subprocess
from util import logger
from database import add_channel, get_channel_by_id, add_video


def get_ytdlp_info(url):
    """Get all needed info from yt-dlp in a single call."""
    try:
        # Get all the info we need in one call using newlines as separators
        format_str = "%(extractor)s\n%(channel)s\n%(channel_id)s\n%(channel_url)s\n%(id)s\n%(title)s\n%(uploader)s/%(upload_date>%Y-%m-%d)s - %(title)s [%(id)s].%(ext)s"

        result = subprocess.run(
            ["./yt-dlp", "--print", format_str, url],
            capture_output=True,
            text=True,
            check=True,
            timeout=30
        )

        lines = result.stdout.strip().split('\n')
        if len(lines) < 7:
            logger.error(f"Unexpected output format from yt-dlp for {url}")
            return None

        return {
            "extractor": lines[0],
            "channel": lines[1],
            "channel_id": lines[2],
            "channel_url": lines[3],
            "video_id": lines[4],
            "title": lines[5],
            "expected_filename": lines[6]
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


def determine_subscription_type(extractor):
    """Determine if URL is a video, playlist, or channel based on extractor."""
    if not extractor:
        return "unknown"

    logger.info(f'Found extractor: {extractor}')

    if extractor == "youtube":
        return "video"
    elif extractor == "youtube:playlist":
        return "playlist"
    elif extractor in ("youtube:channel", "youtube:user"):
        return "channel"
    else:
        return "unknown"


def determine_sync_scope(subscription_type, extractor):
    """Determine the default sync scope based on subscription type."""
    if subscription_type == "video":
        return "single_video"
    elif subscription_type == "playlist":
        return "playlist"
    elif subscription_type == "channel":
        return "full_channel"
    else:
        return "single_video"


def enrich_subscription(subscription):
    """
    Enrich a subscription dict by determining type, sync scope, and adding channel info.
    Returns True if enrichment succeeded, False otherwise.
    """
    url = subscription["url"]
    logger.info(f'Starting enrichment for subscription: {url}')

    # Get all info in a single call
    info = get_ytdlp_info(url)
    if not info:
        logger.error(f"Could not get info for {url}")
        return False

    # Determine subscription type from extractor
    subscription_type = determine_subscription_type(info.get("extractor"))
    subscription["type"] = subscription_type

    if subscription_type == "unknown":
        logger.error(f"Could not determine type for {url}")
        return False

    # Determine sync scope if not already set
    if "sync_scope" not in subscription:
        subscription["sync_scope"] = determine_sync_scope(subscription_type, info.get("extractor"))

    channel_name = info.get("channel", "Unknown Channel")
    channel_id = info.get("channel_id", "")

    subscription["channel"] = channel_name
    subscription["channel_id"] = channel_id
    logger.info(f'Enriched subscription {url} with channel: {channel_name} ({channel_id}) - scope: {subscription["sync_scope"]}')

    # Add/update channel in database
    if channel_id:
        add_channel(channel_id, channel_name)

    # If it's a video, also add it to the videos table
    if subscription_type == "video":
        video_id = info.get("video_id", "")
        title = info.get("title", "Unknown Title")
        expected_filename = info.get("expected_filename", "")

        # Add video to database
        if video_id:
            add_video(video_id, title, channel_id, expected_filename)
            logger.info(f'Added video to database: {title} ({video_id})')

    elif subscription_type in ["playlist", "channel"]:
        # For playlists and channels, we could populate videos later
        logger.info(f'Identified {subscription_type}: {channel_name}')

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