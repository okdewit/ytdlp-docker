"""
Thumbnail Service - Handles channel avatar/thumbnail downloading.
Responsible for downloading and managing channel poster images.
"""
import subprocess
import json
import os
from typing import Optional, List, Dict
from util import logger, YTDLP_BINARY


class ThumbnailService:
    """Service for downloading and managing channel thumbnails."""

    def __init__(self, data_dir: str = "data", timeout: int = 30):
        self.data_dir = data_dir
        self.timeout = timeout

    def download_channel_thumbnail(self, channel_id: str, uploader_name: str) -> Optional[str]:
        """
        Download channel avatar using yt-dlp and save as poster.jpg.

        Args:
            channel_id: YouTube channel ID
            uploader_name: Channel name for directory structure

        Returns:
            Path to downloaded thumbnail or None if failed
        """
        clean_uploader = self._clean_filename_part(uploader_name)
        uploader_dir = os.path.join(self.data_dir, clean_uploader)
        poster_path = os.path.join(uploader_dir, "poster.jpg")

        # Check if poster already exists
        if os.path.exists(poster_path):
            logger.info(f"Poster already exists for {clean_uploader}")
            return poster_path

        # Create directory
        os.makedirs(uploader_dir, exist_ok=True)

        # Try multiple methods to get the avatar
        avatar_url = (self._try_get_avatar_from_channel_info(channel_id, clean_uploader) or
                      self._try_get_avatar_from_about_page(channel_id, clean_uploader) or
                      self._try_get_avatar_from_video(channel_id, clean_uploader))

        if avatar_url and self._download_image_from_url(avatar_url, poster_path):
            logger.info(f"Downloaded avatar for {clean_uploader}")
            return poster_path

        logger.warning(f"All avatar download methods failed for {clean_uploader}")
        return None

    def _try_get_avatar_from_channel_info(self, channel_id: str, clean_uploader: str) -> Optional[str]:
        """Try to get avatar URL from channel info."""
        try:
            logger.info(f"Getting channel avatar info for {clean_uploader}")
            info_result = subprocess.run([
                YTDLP_BINARY, "-J", "--flat-playlist", "--playlist-items", "1",
                f"https://www.youtube.com/channel/{channel_id}"
            ], capture_output=True, text=True, timeout=self.timeout)

            if info_result.returncode != 0:
                return None

            channel_data = json.loads(info_result.stdout)

            # Try avatar_uncropped first (best quality)
            if channel_data.get("avatar_uncropped"):
                logger.info(f"Found avatar_uncropped for {clean_uploader}")
                return channel_data["avatar_uncropped"]

            # Try thumbnails array, filtering out banners
            thumbnails = channel_data.get("thumbnails", [])
            return self._find_best_avatar_thumbnail(thumbnails, clean_uploader)

        except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to get channel info for {clean_uploader}: {e}")
            return None

    def _try_get_avatar_from_about_page(self, channel_id: str, clean_uploader: str) -> Optional[str]:
        """Try to get avatar URL from channel about page."""
        try:
            logger.info(f"Trying about page for {clean_uploader}")
            about_result = subprocess.run([
                YTDLP_BINARY, "-J", "--no-playlist",
                f"https://www.youtube.com/channel/{channel_id}/about"
            ], capture_output=True, text=True, timeout=self.timeout)

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

    def _try_get_avatar_from_video(self, channel_id: str, clean_uploader: str) -> Optional[str]:
        """Try to extract avatar from a video in the channel."""
        try:
            logger.info(f"Trying to extract avatar from videos for {clean_uploader}")
            video_result = subprocess.run([
                YTDLP_BINARY, "-J", "--playlist-items", "1",
                f"https://www.youtube.com/channel/{channel_id}/videos"
            ], capture_output=True, text=True, timeout=self.timeout)

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
            ], capture_output=True, text=True, timeout=self.timeout)

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

    def _find_best_avatar_thumbnail(self, thumbnails: List[Dict], clean_uploader: str) -> Optional[str]:
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

    def _download_image_from_url(self, url: str, file_path: str) -> bool:
        """Download an image from URL using curl."""
        try:
            result = subprocess.run([
                "curl", "-L", "-o", file_path, url
            ], capture_output=True, text=True, timeout=self.timeout)

            return result.returncode == 0 and os.path.exists(file_path)

        except Exception as e:
            logger.error(f"Failed to download image from {url}: {e}")
            return False

    @staticmethod
    def _clean_filename_part(name: str) -> str:
        """Clean a string to be safe for use in filenames."""
        return name.replace("/", "-").replace("\\", "-").strip()