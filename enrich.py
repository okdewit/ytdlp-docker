# enrich.py - Updated for subscriptions
import subprocess
import json
from util import logger
from database import add_channel, get_channel_by_id, add_video


def get_ytdlp_info(url):
    """Get all needed info from yt-dlp using JSON output."""
    try:
        result = subprocess.run(
            ["./yt-dlp", "--flat-playlist", "-J", url],
            capture_output=True,
            text=True,
            check=True,
            timeout=30
        )

        data = json.loads(result.stdout)
        return data

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout getting info for {url}")
        return None
    except subprocess.CalledProcessError as e:
        logger.error(f"yt-dlp failed for {url}: {e.stderr}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from yt-dlp for {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting info for {url}: {e}")
        return None


def determine_subscription_type(data):
    """Determine if URL is a video, playlist, or channel based on JSON data."""
    if not data:
        return "unknown"

    # Check the _type field first
    entry_type = data.get("_type", "")
    extractor = data.get("extractor", "")

    logger.info(f'Found _type: {entry_type}, extractor: {extractor}')

    # Determine type based on _type field
    if entry_type == "playlist":
        # Could be a channel or actual playlist
        extractor_key = data.get("extractor_key", "")
        if extractor_key in ("YoutubeTab", "YoutubeChannel"):
            return "channel"
        else:
            return "playlist"
    elif entry_type == "video":
        return "video"
    elif entry_type in ("channel", "url_transparent"):
        return "channel"

    # Fallback to extractor
    if extractor == "youtube":
        return "video"
    elif extractor == "youtube:playlist":
        return "playlist"
    elif extractor in ("youtube:channel", "youtube:user", "youtube:tab"):
        return "channel"
    else:
        return "unknown"


def enrich_subscription(subscription):
    """
    Enrich a subscription dict by determining type and adding channel info.
    Returns True if enrichment succeeded, False otherwise.
    """
    url = subscription["url"]
    logger.info(f'Starting enrichment for subscription: {url}')

    # Get all info using JSON output
    data = get_ytdlp_info(url)
    if not data:
        logger.error(f"Could not get info for {url}")
        return False

    # Determine subscription type from JSON data
    subscription_type = determine_subscription_type(data)
    subscription["type"] = subscription_type

    if subscription_type == "unknown":
        logger.error(f"Could not determine type for {url}")
        return False

    # Extract channel information
    channel_name = data.get("channel", data.get("uploader", data.get("title", "Unknown Channel")))
    channel_id = data.get("channel_id", data.get("uploader_id", ""))

    subscription["channel"] = channel_name
    subscription["channel_id"] = channel_id
    logger.info(f'Enriched subscription {url} with channel: {channel_name} ({channel_id}) - type: {subscription_type}')

    # Add/update channel in database
    if channel_id:
        add_channel(channel_id, channel_name)

    # If it's a video, add it to the videos table
    if subscription_type == "video":
        video_id = data.get("id", "")
        title = data.get("title", "Unknown Title")
        # Build expected filename
        uploader = data.get("uploader", "Unknown")
        upload_date = data.get("upload_date", "")
        if upload_date and len(upload_date) >= 8:
            formatted_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
        else:
            formatted_date = "Unknown-Date"
        expected_filename = f"{uploader}/{formatted_date} - {title} [{video_id}].mp4"

        if video_id:
            add_video(video_id, title, channel_id, expected_filename)
            logger.info(f'Added video to database: {title} ({video_id})')

    # If it's a channel, populate all videos from the channel
    elif subscription_type == "channel":
        logger.info(f'Channel subscription detected, populating videos for: {channel_name}')
        if channel_id:
            populate_videos_from_channel(channel_id)

    # If it's a playlist, we could populate videos later if needed
    elif subscription_type == "playlist":
        logger.info(f'Playlist subscription detected: {channel_name}')

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
        result = subprocess.run([
            "./yt-dlp",
            "--flat-playlist",
            "-J",
            f"https://www.youtube.com/channel/{channel_id}/videos"
        ], capture_output=True, text=True, check=True, timeout=60)

        data = json.loads(result.stdout)
        entries = data.get("entries", [])

        for entry in entries:
            video_id = entry.get("id", "")
            title = entry.get("title", "Unknown Title")
            uploader = entry.get("uploader", channel["name"])
            upload_date = entry.get("upload_date", "")

            if upload_date and len(upload_date) >= 8:
                formatted_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
            else:
                formatted_date = "Unknown-Date"

            expected_filename = f"{uploader}/{formatted_date} - {title} [{video_id}].mp4"

            if video_id and title:
                add_video(video_id, title, channel_id, expected_filename)

        logger.info(f'Populated {len(entries)} videos for channel: {channel["name"]}')
        return True

    except Exception as e:
        logger.error(f"Error populating videos for channel {channel_id}: {e}")
        return False