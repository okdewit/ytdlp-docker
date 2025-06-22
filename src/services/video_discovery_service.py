"""
Video Discovery Service - Handles channel video population and filename generation.
Responsible for discovering videos in channels and managing video metadata.
"""
from typing import Dict, List, Optional
from util import logger
from database import get_channel_by_id, add_video, video_exists


class VideoDiscoveryService:
    """Service for discovering and managing videos from channels."""

    def __init__(self, metadata_service):
        self.metadata_service = metadata_service

    def populate_videos_from_channel(self, channel_id: str, limit: int = 50) -> bool:
        """
        Populate the videos table with all videos from a channel.

        Args:
            channel_id: The YouTube channel ID
            limit: Maximum number of videos to process (to avoid timeouts)

        Returns:
            True if successful, False otherwise
        """
        channel = get_channel_by_id(channel_id)
        if not channel:
            logger.error(f"Channel not found: {channel_id}")
            return False

        try:
            # Get list of videos using flat-playlist
            entries = self.metadata_service.fetch_channel_video_list(channel_id)
            if not entries:
                return False

            # Limit the number of videos to process
            entries = entries[:limit]
            logger.info(f"Processing {len(entries)} videos for channel: {channel['name']}")

            for i, entry in enumerate(entries):
                self._process_channel_video_entry(entry, i + 1, len(entries), channel)

            logger.info(f'Populated {len(entries)} videos for channel: {channel["name"]}')
            return True

        except Exception as e:
            logger.error(f"Error populating videos for channel {channel_id}: {e}")
            return False

    def generate_video_filename(self, data: Dict, title: str, video_id: str, channel_name: str) -> str:
        """
        Generate expected filename for a video based on metadata.

        Args:
            data: Video metadata from ytdlp
            title: Video title
            video_id: YouTube video ID
            channel_name: Channel name as fallback

        Returns:
            Expected filename string
        """
        # Get uploader with fallback handling
        uploader = data.get("uploader", channel_name)
        if not uploader or uploader == "None":
            uploader = "Unknown"

        # Clean uploader name to be filesystem-safe
        uploader = self._clean_filename_part(uploader)

        # Format upload date
        upload_date = data.get("upload_date", "")
        if upload_date and len(upload_date) >= 8:
            formatted_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
        else:
            formatted_date = "Unknown-Date"

        # Clean title
        clean_title = self._clean_filename_part(title)

        return f"{uploader}/{formatted_date} - {clean_title} [{video_id}].mp4"

    def _process_channel_video_entry(self, entry: Dict, current_index: int, total_count: int, channel: Dict) -> None:
        """Process a single video entry from a channel's video list."""
        video_id = entry.get("id", "")
        if not video_id or video_exists(video_id):
            return

        logger.info(f"Getting detailed info for video {current_index}/{total_count}: {video_id}")

        # Try to get detailed info, fall back to basic info if it fails
        video_data = self.metadata_service.fetch_detailed_video_info(video_id)
        if video_data:
            self._add_video_from_detailed_data(video_data, channel)
        else:
            self._add_video_from_basic_data(entry, channel)

    def _add_video_from_detailed_data(self, video_data: Dict, channel: Dict) -> None:
        """Add video to database using detailed video data."""
        video_id = video_data.get("id", "")
        title = video_data.get("title", "Unknown Title")
        channel_id = channel.get("channel_id")
        channel_name = channel.get("name")

        expected_filename = self.generate_video_filename(video_data, title, video_id, channel_name)

        add_video(video_id, title, channel_id, expected_filename)

    def _add_video_from_basic_data(self, entry: Dict, channel: Dict) -> None:
        """Add video to database using basic entry data (fallback)."""
        video_id = entry.get("id", "")
        title = entry.get("title", "Unknown Title")
        uploader = channel.get("name", "Unknown")
        channel_id = channel.get("channel_id")

        expected_filename = self._generate_video_filename_from_data(
            uploader, "", title, video_id, channel.get("name")
        )

        add_video(video_id, title, channel_id, expected_filename)

    def _generate_video_filename_from_data(self, uploader: str, upload_date: str,
                                           title: str, video_id: str, fallback_uploader: str) -> str:
        """Generate filename from individual data components."""
        # Clean uploader name
        if not uploader or uploader == "None":
            uploader = fallback_uploader if fallback_uploader else "Unknown"
        uploader = self._clean_filename_part(uploader)

        # Format date
        if upload_date and len(upload_date) >= 8:
            formatted_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
        else:
            formatted_date = "Unknown-Date"

        # Clean title
        clean_title = self._clean_filename_part(title)

        return f"{uploader}/{formatted_date} - {clean_title} [{video_id}].mp4"

    @staticmethod
    def _clean_filename_part(name: str) -> str:
        """Clean a string to be safe for use in filenames."""
        return name.replace("/", "-").replace("\\", "-").strip()