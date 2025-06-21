# enrich.py - Updated for subscriptions with local thumbnails
import subprocess
import json
import os
from util import logger
from database import add_channel, get_channel_by_id, add_video, video_exists


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


def download_channel_thumbnail(channel_id, uploader_name):
    """Download channel avatar using yt-dlp and save as poster.jpg."""
    try:
        # Clean uploader name for filesystem
        clean_uploader = uploader_name.replace("/", "-").replace("\\", "-").strip()

        # Create uploader directory if it doesn't exist
        uploader_dir = os.path.join("data", clean_uploader)
        os.makedirs(uploader_dir, exist_ok=True)

        poster_path = os.path.join(uploader_dir, "poster.jpg")

        # Check if poster already exists
        if os.path.exists(poster_path):
            logger.info(f"Poster already exists for {clean_uploader}")
            return poster_path

        # Method 1: Get channel info to extract avatar URL
        logger.info(f"Getting channel avatar info for {clean_uploader}")
        info_result = subprocess.run([
            "./yt-dlp",
            "-J",
            "--flat-playlist",
            "--playlist-items", "1",  # Only get info for first item
            f"https://www.youtube.com/channel/{channel_id}"
        ], capture_output=True, text=True, timeout=30)

        if info_result.returncode == 0:
            try:
                channel_data = json.loads(info_result.stdout)

                # Look for channel avatar in various fields
                avatar_url = None

                # Try avatar_uncropped first (best quality profile picture)
                if channel_data.get("avatar_uncropped"):
                    avatar_url = channel_data["avatar_uncropped"]
                    logger.info(f"Found avatar_uncropped for {clean_uploader}")

                # Try thumbnails array, but filter out banners
                elif channel_data.get("thumbnails"):
                    thumbnails = channel_data["thumbnails"]
                    if thumbnails:
                        # Filter out banner images (usually very wide) and look for square-ish avatars
                        avatar_candidates = []
                        for thumb in thumbnails:
                            width = thumb.get("width", 0)
                            height = thumb.get("height", 0)
                            url = thumb.get("url", "")

                            # Skip banner images (aspect ratio > 2:1 or contains banner indicators)
                            if width > 0 and height > 0:
                                aspect_ratio = width / height
                                # Look for roughly square images (profile pics) and avoid banners
                                if (0.8 <= aspect_ratio <= 1.25 and
                                    "fcrop64" not in url and
                                    "banner" not in url.lower()):
                                    avatar_candidates.append(thumb)

                        if avatar_candidates:
                            # Get the highest resolution square avatar
                            best_thumb = max(avatar_candidates, key=lambda x: (x.get("width", 0) * x.get("height", 0)))
                            avatar_url = best_thumb.get("url")
                            logger.info(f"Found square avatar thumbnail for {clean_uploader}")
                        else:
                            # Fallback to smallest thumbnail (likely to be avatar, not banner)
                            smallest_thumb = min(thumbnails, key=lambda x: (x.get("width", 0) * x.get("height", 0)))
                            avatar_url = smallest_thumb.get("url")
                            logger.info(f"Using smallest thumbnail as avatar fallback for {clean_uploader}")

                # Skip direct thumbnail field as it's often the banner

                # If we found an avatar URL, download it using wget or curl
                if avatar_url:
                    logger.info(f"Downloading avatar from {avatar_url}")

                    # Try using curl to download the image directly
                    curl_result = subprocess.run([
                        "curl", "-L", "-o", poster_path, avatar_url
                    ], capture_output=True, text=True, timeout=30)

                    if curl_result.returncode == 0 and os.path.exists(poster_path):
                        logger.info(f"Downloaded avatar using curl for {clean_uploader}")
                        return poster_path

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse channel data for {uploader_name}: {e}")

        # Method 2: Try getting avatar from /about page
        logger.info(f"Fallback: trying to get avatar from about page for {clean_uploader}")
        about_result = subprocess.run([
            "./yt-dlp",
            "-J",
            "--no-playlist",
            f"https://www.youtube.com/channel/{channel_id}/about"
        ], capture_output=True, text=True, timeout=30)

        if about_result.returncode == 0:
            try:
                about_data = json.loads(about_result.stdout)
                # Look specifically for avatar fields, not thumbnail (which might be banner)
                avatar_url = about_data.get("avatar_uncropped")

                if avatar_url:
                    logger.info(f"Found avatar from about page: {avatar_url}")
                    curl_result = subprocess.run([
                        "curl", "-L", "-o", poster_path, avatar_url
                    ], capture_output=True, text=True, timeout=30)

                    if curl_result.returncode == 0 and os.path.exists(poster_path):
                        logger.info(f"Downloaded avatar from about page for {clean_uploader}")
                        return poster_path

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse about page data for {uploader_name}: {e}")

        # Method 3: Try extracting avatar from a single video from the channel
        logger.info(f"Final fallback: trying to extract avatar from channel videos for {clean_uploader}")
        video_result = subprocess.run([
            "./yt-dlp",
            "-J",
            "--playlist-items", "1",
            f"https://www.youtube.com/channel/{channel_id}/videos"
        ], capture_output=True, text=True, timeout=30)

        if video_result.returncode == 0:
            try:
                video_data = json.loads(video_result.stdout)
                entries = video_data.get("entries", [])

                if entries:
                    # Get detailed info for the first video to extract uploader avatar
                    first_video = entries[0]
                    video_id = first_video.get("id")

                    if video_id:
                        detailed_result = subprocess.run([
                            "./yt-dlp",
                            "-J",
                            f"https://www.youtube.com/watch?v={video_id}"
                        ], capture_output=True, text=True, timeout=30)

                        if detailed_result.returncode == 0:
                            detailed_data = json.loads(detailed_result.stdout)

                            # Look for uploader avatar
                            avatar_url = (detailed_data.get("uploader_avatar") or
                                        detailed_data.get("channel_avatar") or
                                        detailed_data.get("uploader_thumbnail"))

                            if avatar_url:
                                logger.info(f"Found uploader avatar from video: {avatar_url}")
                                curl_result = subprocess.run([
                                    "curl", "-L", "-o", poster_path, avatar_url
                                ], capture_output=True, text=True, timeout=30)

                                if curl_result.returncode == 0 and os.path.exists(poster_path):
                                    logger.info(f"Downloaded uploader avatar for {clean_uploader}")
                                    return poster_path

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse video data for {uploader_name}: {e}")

        logger.warning(f"All avatar download methods failed for {clean_uploader}")
        return None

    except Exception as e:
        logger.error(f"Error downloading avatar for {uploader_name}: {e}")
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

        # Download channel thumbnail
        if channel_name:
            poster_path = download_channel_thumbnail(channel_id, channel_name)
            if poster_path:
                subscription["poster_path"] = poster_path

    # If it's a video, add it to the videos table
    if subscription_type == "video":
        video_id = data.get("id", "")
        title = data.get("title", "Unknown Title")

        # Get uploader with better fallback handling
        uploader = data.get("uploader", channel_name)
        if not uploader or uploader == "None":
            uploader = "Unknown"

        # Clean uploader name to be filesystem-safe
        uploader = uploader.replace("/", "-").replace("\\", "-").strip()

        upload_date = data.get("upload_date", "")
        if upload_date and len(upload_date) >= 8:
            formatted_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
        else:
            formatted_date = "Unknown-Date"

        # Clean title to be filesystem-safe
        clean_title = title.replace("/", "-").replace("\\", "-").strip()

        expected_filename = f"{uploader}/{formatted_date} - {clean_title} [{video_id}].mp4"

        if video_id:
            add_video(video_id, title, channel_id, expected_filename)
            logger.info(f'Added video to database: {title} ({video_id})')

            # Also download thumbnail for single video's channel
            if channel_id and channel_name:
                download_channel_thumbnail(channel_id, channel_name)

    # If it's a channel, populate all videos from the channel
    elif subscription_type == "channel":
        logger.info(f'Channel subscription detected, populating videos for: {channel_name}')
        if channel_id:
            populate_videos_from_channel(channel_id)

    # If it's a playlist, we could populate videos later if needed
    elif subscription_type == "playlist":
        logger.info(f'Playlist subscription detected: {channel_name}')

    return True


def populate_videos_from_channel(channel_id, limit=50):
    """
    Populate the videos table with all videos from a channel.
    This can be run separately to discover all videos in a channel.

    Args:
        channel_id: The YouTube channel ID
        limit: Maximum number of videos to process (to avoid timeouts)
    """
    channel = get_channel_by_id(channel_id)
    if not channel:
        logger.error(f"Channel not found: {channel_id}")
        return False

    try:
        # First, get the list of videos using flat-playlist
        result = subprocess.run([
            "./yt-dlp",
            "--flat-playlist",
            "-J",
            f"https://www.youtube.com/channel/{channel_id}/videos"
        ], capture_output=True, text=True, check=True, timeout=60)

        data = json.loads(result.stdout)
        entries = data.get("entries", [])

        # Limit the number of videos to process
        entries = entries[:limit]

        logger.info(f"Processing {len(entries)} videos for channel: {channel['name']}")

        for i, entry in enumerate(entries):
            video_id = entry.get("id", "")
            if not video_id:
                continue

            # Check if video already exists
            if video_exists(video_id):
                continue

            logger.info(f"Getting detailed info for video {i + 1}/{len(entries)}: {video_id}")

            # Get detailed info for each video to get upload_date
            try:
                video_result = subprocess.run([
                    "./yt-dlp",
                    "-J",
                    f"https://www.youtube.com/watch?v={video_id}"
                ], capture_output=True, text=True, check=True, timeout=30)

                video_data = json.loads(video_result.stdout)

                title = video_data.get("title", "Unknown Title")
                uploader = video_data.get("uploader", channel["name"])
                upload_date = video_data.get("upload_date", "")

                # Clean uploader name
                if not uploader or uploader == "None":
                    uploader = channel["name"] if channel["name"] else "Unknown"
                uploader = uploader.replace("/", "-").replace("\\", "-").strip()

                # Format date
                if upload_date and len(upload_date) >= 8:
                    formatted_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
                else:
                    formatted_date = "Unknown-Date"

                # Clean title
                clean_title = title.replace("/", "-").replace("\\", "-").strip()

                expected_filename = f"{uploader}/{formatted_date} - {clean_title} [{video_id}].mp4"

                add_video(video_id, title, channel_id, expected_filename)

            except Exception as e:
                logger.warning(f"Failed to get detailed info for video {video_id}: {e}")
                # Fallback to basic info from flat playlist
                title = entry.get("title", "Unknown Title")
                uploader = channel["name"] if channel["name"] else "Unknown"
                uploader = uploader.replace("/", "-").replace("\\", "-").strip()
                clean_title = title.replace("/", "-").replace("\\", "-").strip()
                expected_filename = f"{uploader}/Unknown-Date - {clean_title} [{video_id}].mp4"
                add_video(video_id, title, channel_id, expected_filename)

        logger.info(f'Populated {len(entries)} videos for channel: {channel["name"]}')
        return True

    except Exception as e:
        logger.error(f"Error populating videos for channel {channel_id}: {e}")
        return False