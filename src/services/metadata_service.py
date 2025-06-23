"""
Metadata Service - Simplified without filename generation complexity.
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

    def get_video_filesize(self, video_id: str) -> Optional[int]:
        """
        Get the filesize for a video using yt-dlp.

        Args:
            video_id: YouTube video ID

        Returns:
            Filesize in bytes or None if failed/unavailable
        """
        try:
            result = subprocess.run([
                YTDLP_BINARY, "--print", "%(filesize,filesize_approx)s",
                f"https://www.youtube.com/watch?v={video_id}"
            ], capture_output=True, text=True, check=True, timeout=self.timeout)

            if result.returncode == 0:
                filesize_str = result.stdout.strip()

                # Handle different possible outputs
                if filesize_str and filesize_str != "NA" and filesize_str != "None":
                    try:
                        # Try to parse as integer (bytes)
                        filesize = int(float(filesize_str))
                        if filesize > 0:
                            logger.debug(f"Got filesize for {video_id}: {filesize} bytes")
                            return filesize
                    except (ValueError, TypeError):
                        logger.debug(f"Could not parse filesize '{filesize_str}' for {video_id}")

                logger.debug(f"No valid filesize available for {video_id}")
                return None

        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout getting filesize for {video_id}")
        except subprocess.CalledProcessError as e:
            logger.warning(f"yt-dlp failed to get filesize for {video_id}: {e.stderr}")
        except Exception as e:
            logger.warning(f"Unexpected error getting filesize for {video_id}: {e}")

        return None

    def get_video_metadata_with_filesize(self, video_id: str) -> Dict:
        """
        Get comprehensive metadata for a video including filesize.

        Args:
            video_id: YouTube video ID

        Returns:
            Dict with metadata including filesize
        """
        # Get detailed metadata
        detailed_data = self.fetch_detailed_video_info(video_id)

        # Get filesize separately (more reliable than JSON metadata)
        filesize = self.get_video_filesize(video_id)

        result = {
            "video_id": video_id,
            "filesize": filesize
        }

        if detailed_data:
            result.update({
                "title": detailed_data.get("title", "Unknown Title"),
                "uploader": detailed_data.get("uploader", "Unknown"),
                "channel_id": detailed_data.get("channel_id", ""),
                "duration": detailed_data.get("duration"),
                "upload_date": detailed_data.get("upload_date")
            })

        return result

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

    def fetch_detailed_video_info(self, video_id: str) -> Optional[Dict]:
        """
        Fetch detailed info for a single video.

        Args:
            video_id: YouTube video ID

        Returns:
            Dict containing detailed video metadata or None if failed
        """
        try:
            result = subprocess.run([
                YTDLP_BINARY, "-J", f"https://www.youtube.com/watch?v={video_id}"
            ], capture_output=True, text=True, check=True, timeout=self.timeout)

            return json.loads(result.stdout)

        except Exception as e:
            logger.warning(f"Failed to get detailed info for video {video_id}: {e}")
            return None