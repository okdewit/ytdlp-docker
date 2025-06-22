# enrich.py - Refactored for better readability and separation of concerns
import subprocess
import json
import os
from util import logger
from database import add_channel, get_channel_by_id, add_video, video_exists
from util import YTDLP_BINARY


def enrich_subscription(subscription):
    """
    Main orchestration function - enriches a subscription with metadata.
    Returns True if enrichment succeeded, False otherwise.
    """
    url = subscription["url"]
    logger.info(f'Starting enrichment for subscription: {url}')

    # Step 1: Get metadata
    data = _fetch_url_metadata(url)
    if not data:
        logger.error(f"Could not get info for {url}")
        return False

    # Step 2: Determine and set subscription type
    subscription_type = _determine_subscription_type(data)
    if subscription_type == "unknown":
        logger.error(f"Could not determine type for {url}")
        return False

    subscription["type"] = subscription_type

    # Step 3: Extract and set channel information
    _extract_channel_info(subscription, data)

    # Step 4: Handle database operations for channel
    _handle_channel_operations(subscription)

    # Step 5: Handle type-specific operations
    _handle_type_specific_operations(subscription, data, subscription_type)

    logger.info(f'Successfully enriched subscription {url} - type: {subscription_type}')
    return True


def _fetch_url_metadata(url):
    """Fetch metadata from yt-dlp using JSON output."""
    try:
        result = subprocess.run(
            [YTDLP_BINARY, "--flat-playlist", "-J", url],
            capture_output=True,
            text=True,
            check=True,
            timeout=30
        )
        return json.loads(result.stdout)

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout getting info for {url}")
    except subprocess.CalledProcessError as e:
        logger.error(f"yt-dlp failed for {url}: {e.stderr}")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from yt-dlp for {url}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error getting info for {url}: {e}")

    return None


def _determine_subscription_type(data):
    """Determine if URL is a video, playlist, or channel based on JSON data."""
    entry_type = data.get("_type", "")
    extractor = data.get("extractor", "")
    extractor_key = data.get("extractor_key", "")

    logger.info(f'Found _type: {entry_type}, extractor: {extractor}')

    # Check the _type field first
    if entry_type == "playlist":
        return "channel" if extractor_key in ("YoutubeTab", "YoutubeChannel") else "playlist"
    elif entry_type == "video":
        return "video"
    elif entry_type in ("channel", "url_transparent"):
        return "channel"

    # Fallback to extractor
    type_mapping = {
        "youtube": "video",
        "youtube:playlist": "playlist",
        "youtube:channel": "channel",
        "youtube:user": "channel",
        "youtube:tab": "channel"
    }

    return type_mapping.get(extractor, "unknown")


def _extract_channel_info(subscription, data):
    """Extract channel information from metadata and add to subscription."""
    channel_name = data.get("channel", data.get("uploader", data.get("title", "Unknown Channel")))
    channel_id = data.get("channel_id", data.get("uploader_id", ""))

    subscription["channel"] = channel_name
    subscription["channel_id"] = channel_id

    logger.info(f'Extracted channel info: {channel_name} ({channel_id})')


def _handle_channel_operations(subscription):
    """Handle database operations and thumbnail download for the channel."""
    channel_id = subscription.get("channel_id")
    channel_name = subscription.get("channel")

    if not channel_id:
        return

    # Add/update channel in database
    add_channel(channel_id, channel_name)

    # Download channel thumbnail
    if channel_name:
        poster_path = _download_channel_thumbnail(channel_id, channel_name)
        if poster_path:
            subscription["poster_path"] = poster_path


def _handle_type_specific_operations(subscription, data, subscription_type):
    """Handle operations specific to subscription type (video, channel, playlist)."""
    if subscription_type == "video":
        _handle_video_subscription(subscription, data)
    elif subscription_type == "channel":
        _handle_channel_subscription(subscription)
    elif subscription_type == "playlist":
        logger.info(f'Playlist subscription detected: {subscription.get("channel")}')


def _handle_video_subscription(subscription, data):
    """Handle video-specific operations: add to database and download thumbnail."""
    video_id = data.get("id", "")
    if not video_id:
        return

    title = data.get("title", "Unknown Title")
    channel_id = subscription.get("channel_id")
    channel_name = subscription.get("channel")

    expected_filename = _generate_video_filename(data, title, video_id, channel_name)

    add_video(video_id, title, channel_id, expected_filename)
    logger.info(f'Added video to database: {title} ({video_id})')

    # Download thumbnail for single video's channel
    if channel_id and channel_name:
        _download_channel_thumbnail(channel_id, channel_name)


def _handle_channel_subscription(subscription):
    """Handle channel-specific operations: populate all videos."""
    channel_name = subscription.get("channel")
    channel_id = subscription.get("channel_id")

    logger.info(f'Channel subscription detected, populating videos for: {channel_name}')
    if channel_id:
        populate_videos_from_channel(channel_id)


def _generate_video_filename(data, title, video_id, channel_name):
    """Generate expected filename for a video based on metadata."""
    # Get uploader with fallback handling
    uploader = data.get("uploader", channel_name)
    if not uploader or uploader == "None":
        uploader = "Unknown"

    # Clean uploader name to be filesystem-safe
    uploader = _clean_filename_part(uploader)

    # Format upload date
    upload_date = data.get("upload_date", "")
    if upload_date and len(upload_date) >= 8:
        formatted_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
    else:
        formatted_date = "Unknown-Date"

    # Clean title
    clean_title = _clean_filename_part(title)

    return f"{uploader}/{formatted_date} - {clean_title} [{video_id}].mp4"


def _clean_filename_part(name):
    """Clean a string to be safe for use in filenames."""
    return name.replace("/", "-").replace("\\", "-").strip()


def _download_channel_thumbnail(channel_id, uploader_name):
    """
    Download channel avatar using yt-dlp and save as poster.jpg.
    Returns path to downloaded thumbnail or None if failed.
    """
    clean_uploader = _clean_filename_part(uploader_name)
    uploader_dir = os.path.join("data", clean_uploader)
    poster_path = os.path.join(uploader_dir, "poster.jpg")

    # Check if poster already exists
    if os.path.exists(poster_path):
        logger.info(f"Poster already exists for {clean_uploader}")
        return poster_path

    # Create directory
    os.makedirs(uploader_dir, exist_ok=True)

    # Try multiple methods to get the avatar
    avatar_url = (_try_get_avatar_from_channel_info(channel_id, clean_uploader) or
                  _try_get_avatar_from_about_page(channel_id, clean_uploader) or
                  _try_get_avatar_from_video(channel_id, clean_uploader))

    if avatar_url and _download_image_from_url(avatar_url, poster_path):
        logger.info(f"Downloaded avatar for {clean_uploader}")
        return poster_path

    logger.warning(f"All avatar download methods failed for {clean_uploader}")
    return None


def _try_get_avatar_from_channel_info(channel_id, clean_uploader):
    """Try to get avatar URL from channel info."""
    try:
        logger.info(f"Getting channel avatar info for {clean_uploader}")
        info_result = subprocess.run([
            YTDLP_BINARY, "-J", "--flat-playlist", "--playlist-items", "1",
            f"https://www.youtube.com/channel/{channel_id}"
        ], capture_output=True, text=True, timeout=30)

        if info_result.returncode != 0:
            return None

        channel_data = json.loads(info_result.stdout)

        # Try avatar_uncropped first (best quality)
        if channel_data.get("avatar_uncropped"):
            logger.info(f"Found avatar_uncropped for {clean_uploader}")
            return channel_data["avatar_uncropped"]

        # Try thumbnails array, filtering out banners
        thumbnails = channel_data.get("thumbnails", [])
        return _find_best_avatar_thumbnail(thumbnails, clean_uploader)

    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
        logger.warning(f"Failed to get channel info for {clean_uploader}: {e}")
        return None


def _try_get_avatar_from_about_page(channel_id, clean_uploader):
    """Try to get avatar URL from channel about page."""
    try:
        logger.info(f"Trying about page for {clean_uploader}")
        about_result = subprocess.run([
            YTDLP_BINARY, "-J", "--no-playlist",
            f"https://www.youtube.com/channel/{channel_id}/about"
        ], capture_output=True, text=True, timeout=30)

        if about_result.returncode != 0:
            return None

        about_data = json.loads(about_result.stdout)
        avatar_url = about_data.get("avatar_uncropped")

        if avatar_url:
            logger.info(f"Found avatar from about page for {clean_uploader}")
            return avatar_url

    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
        logger.warning(f"Failed to get about page for {clean_uploader}: {e}")

    return None


def _try_get_avatar_from_video(channel_id, clean_uploader):
    """Try to extract avatar from a video in the channel."""
    try:
        logger.info(f"Trying to extract avatar from videos for {clean_uploader}")
        video_result = subprocess.run([
            YTDLP_BINARY, "-J", "--playlist-items", "1",
            f"https://www.youtube.com/channel/{channel_id}/videos"
        ], capture_output=True, text=True, timeout=30)

        if video_result.returncode != 0:
            return None

        video_data = json.loads(video_result.stdout)
        entries = video_data.get("entries", [])

        if not entries:
            return None

        # Get detailed info for the first video
        video_id = entries[0].get("id")
        if not video_id:
            return None

        detailed_result = subprocess.run([
            YTDLP_BINARY, "-J", f"https://www.youtube.com/watch?v={video_id}"
        ], capture_output=True, text=True, timeout=30)

        if detailed_result.returncode != 0:
            return None

        detailed_data = json.loads(detailed_result.stdout)
        avatar_url = (detailed_data.get("uploader_avatar") or
                     detailed_data.get("channel_avatar") or
                     detailed_data.get("uploader_thumbnail"))

        if avatar_url:
            logger.info(f"Found uploader avatar from video for {clean_uploader}")
            return avatar_url

    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
        logger.warning(f"Failed to get video avatar for {clean_uploader}: {e}")

    return None


def _find_best_avatar_thumbnail(thumbnails, clean_uploader):
    """Find the best avatar thumbnail from a list, avoiding banners."""
    if not thumbnails:
        return None

    avatar_candidates = []
    for thumb in thumbnails:
        width = thumb.get("width", 0)
        height = thumb.get("height", 0)
        url = thumb.get("url", "")

        # Skip banner images (wide aspect ratio or contains banner indicators)
        if width > 0 and height > 0:
            aspect_ratio = width / height
            if (0.8 <= aspect_ratio <= 1.25 and
                "fcrop64" not in url and
                "banner" not in url.lower()):
                avatar_candidates.append(thumb)

    if avatar_candidates:
        # Get the highest resolution square avatar
        best_thumb = max(avatar_candidates, key=lambda x: (x.get("width", 0) * x.get("height", 0)))
        logger.info(f"Found square avatar thumbnail for {clean_uploader}")
        return best_thumb.get("url")

    # Fallback to smallest thumbnail
    if thumbnails:
        smallest_thumb = min(thumbnails, key=lambda x: (x.get("width", 0) * x.get("height", 0)))
        logger.info(f"Using smallest thumbnail as avatar fallback for {clean_uploader}")
        return smallest_thumb.get("url")

    return None


def _download_image_from_url(url, file_path):
    """Download an image from URL using curl."""
    try:
        result = subprocess.run([
            "curl", "-L", "-o", file_path, url
        ], capture_output=True, text=True, timeout=30)

        return result.returncode == 0 and os.path.exists(file_path)

    except Exception as e:
        logger.error(f"Failed to download image from {url}: {e}")
        return False


def populate_videos_from_channel(channel_id, limit=50):
    """
    Populate the videos table with all videos from a channel.

    Args:
        channel_id: The YouTube channel ID
        limit: Maximum number of videos to process (to avoid timeouts)
    """
    channel = get_channel_by_id(channel_id)
    if not channel:
        logger.error(f"Channel not found: {channel_id}")
        return False

    try:
        # Get list of videos using flat-playlist
        entries = _fetch_channel_video_list(channel_id)
        if not entries:
            return False

        # Limit the number of videos to process
        entries = entries[:limit]
        logger.info(f"Processing {len(entries)} videos for channel: {channel['name']}")

        for i, entry in enumerate(entries):
            _process_channel_video_entry(entry, i + 1, len(entries), channel)

        logger.info(f'Populated {len(entries)} videos for channel: {channel["name"]}')
        return True

    except Exception as e:
        logger.error(f"Error populating videos for channel {channel_id}: {e}")
        return False


def _fetch_channel_video_list(channel_id):
    """Fetch the list of videos from a channel."""
    try:
        result = subprocess.run([
            YTDLP_BINARY, "--flat-playlist", "-J",
            f"https://www.youtube.com/channel/{channel_id}/videos"
        ], capture_output=True, text=True, check=True, timeout=60)

        data = json.loads(result.stdout)
        return data.get("entries", [])

    except Exception as e:
        logger.error(f"Failed to fetch video list for channel {channel_id}: {e}")
        return []


def _process_channel_video_entry(entry, current_index, total_count, channel):
    """Process a single video entry from a channel's video list."""
    video_id = entry.get("id", "")
    if not video_id or video_exists(video_id):
        return

    logger.info(f"Getting detailed info for video {current_index}/{total_count}: {video_id}")

    # Try to get detailed info, fall back to basic info if it fails
    video_data = _fetch_detailed_video_info(video_id)
    if video_data:
        _add_video_from_detailed_data(video_data, channel)
    else:
        _add_video_from_basic_data(entry, channel)


def _fetch_detailed_video_info(video_id):
    """Fetch detailed info for a single video."""
    try:
        result = subprocess.run([
            YTDLP_BINARY, "-J", f"https://www.youtube.com/watch?v={video_id}"
        ], capture_output=True, text=True, check=True, timeout=30)

        return json.loads(result.stdout)

    except Exception as e:
        logger.warning(f"Failed to get detailed info for video {video_id}: {e}")
        return None


def _add_video_from_detailed_data(video_data, channel):
    """Add video to database using detailed video data."""
    video_id = video_data.get("id", "")
    title = video_data.get("title", "Unknown Title")
    uploader = video_data.get("uploader", channel["name"])
    upload_date = video_data.get("upload_date", "")

    expected_filename = _generate_video_filename_from_data(
        uploader, upload_date, title, video_id, channel["name"]
    )

    add_video(video_id, title, channel["channel_id"], expected_filename)


def _add_video_from_basic_data(entry, channel):
    """Add video to database using basic entry data (fallback)."""
    video_id = entry.get("id", "")
    title = entry.get("title", "Unknown Title")
    uploader = channel["name"] if channel["name"] else "Unknown"

    expected_filename = _generate_video_filename_from_data(
        uploader, "", title, video_id, channel["name"]
    )

    add_video(video_id, title, channel["channel_id"], expected_filename)


def _generate_video_filename_from_data(uploader, upload_date, title, video_id, fallback_uploader):
    """Generate filename from individual data components."""
    # Clean uploader name
    if not uploader or uploader == "None":
        uploader = fallback_uploader if fallback_uploader else "Unknown"
    uploader = _clean_filename_part(uploader)

    # Format date
    if upload_date and len(upload_date) >= 8:
        formatted_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
    else:
        formatted_date = "Unknown-Date"

    # Clean title
    clean_title = _clean_filename_part(title)

    return f"{uploader}/{formatted_date} - {clean_title} [{video_id}].mp4"


# Legacy function name for backward compatibility
get_ytdlp_info = _fetch_url_metadata
determine_subscription_type = _determine_subscription_type
download_channel_thumbnail = _download_channel_thumbnail