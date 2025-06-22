"""
Metadata Service - Enhanced with yt-dlp filename generation.
"""
import subprocess
import json
import shlex
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

    def get_ytdlp_filename(self, video_id: str, parameters: str) -> Optional[str]:
        """
        Get the actual filename that yt-dlp would generate for a video using essential parameters.

        Args:
            video_id: YouTube video ID
            parameters: Full yt-dlp parameters string

        Returns:
            Expected filename or None if failed
        """
        try:
            # Parse the parameters and extract only filename-relevant ones
            import shlex
            args = shlex.split(parameters)

            # Filter to only include parameters that affect filename generation
            filename_relevant_args = []
            i = 0
            while i < len(args):
                arg = args[i]

                # Include these parameters that affect filename
                if arg in ['-f', '--format']:
                    filename_relevant_args.extend([arg, args[i + 1]])
                    i += 2
                elif arg in ['-o', '--output']:
                    filename_relevant_args.extend([arg, args[i + 1]])
                    i += 2
                elif arg in ['--merge-output-format']:
                    filename_relevant_args.extend([arg, args[i + 1]])
                    i += 2
                elif arg in ['-P']:
                    filename_relevant_args.extend([arg, args[i + 1]])
                    i += 2
                elif arg.startswith('-f=') or arg.startswith('--format='):
                    filename_relevant_args.append(arg)
                    i += 1
                elif arg.startswith('-o=') or arg.startswith('--output='):
                    filename_relevant_args.append(arg)
                    i += 1
                elif arg.startswith('--merge-output-format='):
                    filename_relevant_args.append(arg)
                    i += 1
                else:
                    i += 1

            cmd = [YTDLP_BINARY, "--print", "filename"] + filename_relevant_args + [f"https://www.youtube.com/watch?v={video_id}"]

            logger.debug(f"Running yt-dlp filename command: {' '.join(cmd)}")

            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=self.timeout)

            if result.returncode == 0:
                filename = result.stdout.strip()

                # Remove the data/ prefix if present (since we add it back in check_video_downloaded)
                if filename.startswith("data/"):
                    filename = filename[5:]  # Remove "data/" prefix

                logger.debug(f"yt-dlp would generate filename: {filename}")
                return filename
            else:
                logger.warning(f"yt-dlp filename command failed with return code {result.returncode}")
                if result.stderr:
                    logger.warning(f"yt-dlp stderr: {result.stderr}")

        except Exception as e:
            logger.warning(f"Failed to get yt-dlp filename for {video_id}: {e}")

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