"""
Metadata Service - Handles ytdlp interaction and JSON parsing.
Responsible for fetching metadata and determining subscription types.
"""
import subprocess
import json
from typing import Dict, Optional, List
from util import logger, YTDLP_BINARY


class MetadataService:
    """Service for fetching and parsing ytdlp metadata."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def fetch_url_metadata(self, url: str) -> Optional[Dict]:
        """
        Fetch metadata from yt-dlp using JSON output.

        Args:
            url: The URL to fetch metadata for

        Returns:
            Dict containing metadata or None if failed
        """
        try:
            result = subprocess.run(
                [YTDLP_BINARY, "--flat-playlist", "-J", url],
                capture_output=True,
                text=True,
                check=True,
                timeout=self.timeout
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

    def determine_subscription_type(self, data: Dict) -> str:
        """
        Determine if URL is a video, playlist, or channel based on JSON data.

        Args:
            data: Metadata dictionary from ytdlp

        Returns:
            String indicating type: 'video', 'playlist', 'channel', or 'unknown'
        """
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

    def extract_channel_info(self, data: Dict) -> Dict[str, str]:
        """
        Extract channel information from metadata.

        Args:
            data: Metadata dictionary from ytdlp

        Returns:
            Dict with 'channel' and 'channel_id' keys
        """
        channel_name = data.get("channel", data.get("uploader", data.get("title", "Unknown Channel")))
        channel_id = data.get("channel_id", data.get("uploader_id", ""))

        logger.info(f'Extracted channel info: {channel_name} ({channel_id})')

        return {
            "channel": channel_name,
            "channel_id": channel_id
        }

    def fetch_channel_video_list(self, channel_id: str, timeout: int = 60) -> List[Dict]:
        """
        Fetch the list of videos from a channel.

        Args:
            channel_id: YouTube channel ID
            timeout: Request timeout in seconds

        Returns:
            List of video entry dictionaries
        """
        try:
            result = subprocess.run([
                YTDLP_BINARY, "--flat-playlist", "-J",
                f"https://www.youtube.com/channel/{channel_id}/videos"
            ], capture_output=True, text=True, check=True, timeout=timeout)

            data = json.loads(result.stdout)
            return data.get("entries", [])

        except Exception as e:
            logger.error(f"Failed to fetch video list for channel {channel_id}: {e}")
            return []

    def fetch_detailed_video_info(self, video_id: str, output_template: str = None) -> Optional[Dict]:
        """
        Fetch detailed info for a single video, optionally with filename generation.
        """
        cmd = [YTDLP_BINARY, "-J", f"https://www.youtube.com/watch?v={video_id}"]

        if output_template:
            cmd.extend(["-o", output_template])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=self.timeout)
            data = json.loads(result.stdout)

            # If we used an output template, yt-dlp includes the filename in the response
            if output_template and "requested_downloads" in data:
                # yt-dlp puts the actual filename in requested_downloads[0]["filename"]
                filename = data["requested_downloads"][0].get("filename")
                if filename:
                    data["expected_filename"] = filename

            return data
        except Exception as e:
            logger.warning(f"Failed to get detailed info for video {video_id}: {e}")
            return None