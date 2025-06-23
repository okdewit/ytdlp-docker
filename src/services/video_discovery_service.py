"""
Video Discovery Service - Simplified without filename generation complexity.
"""
from typing import Dict, List, Optional
from util import logger
from database import get_channel_by_id, add_video, video_exists, get_parameters


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

    def process_single_video_with_filesize(self, video_id: str, channel_id: str = None) -> Optional[Dict]:
        """
        Process a single video, getting both metadata and filesize.

        Args:
            video_id: YouTube video ID
            channel_id: Optional channel ID for database relations

        Returns:
            Dict with video data or None if failed
        """
        try:
            # Get comprehensive metadata including filesize
            metadata = self.metadata_service.get_video_metadata_with_filesize(video_id)

            if not metadata:
                logger.error(f"Could not get metadata for video {video_id}")
                return None

            # Add to database with filesize
            video_data = add_video(
                video_id=video_id,
                title=metadata.get("title", "Unknown Title"),
                channel_id=channel_id,
                filesize=metadata.get("filesize")
            )

            logger.info(f"Processed video with filesize: {metadata.get('title')} - {metadata.get('filesize', 'unknown')} bytes")
            return video_data

        except Exception as e:
            logger.error(f"Error processing video {video_id}: {e}")
            return None

    def _process_channel_video_entry(self, entry: Dict, current_index: int, total_count: int, channel: Dict) -> None:
        """Process a single video entry from a channel's video list."""
        video_id = entry.get("id", "")
        if not video_id or video_exists(video_id):
            return

        logger.info(f"Getting detailed info for video {current_index}/{total_count}: {video_id}")

        # Get filesize separately for better reliability
        filesize = self.metadata_service.get_video_filesize(video_id)

        # Try to get detailed info, fall back to basic info if it fails
        video_data = self.metadata_service.fetch_detailed_video_info(video_id)
        if video_data:
            self._add_video_from_detailed_data(video_data, channel, filesize)
        else:
            self._add_video_from_basic_data(entry, channel, filesize)

    @staticmethod
    def _add_video_from_detailed_data(video_data: Dict, channel: Dict, filesize: Optional[int]) -> None:
        """Add video to database using detailed video data."""
        video_id = video_data.get("id", "")
        title = video_data.get("title", "Unknown Title")
        channel_id = channel.get("channel_id")

        add_video(video_id, title, channel_id, filesize)

    @staticmethod
    def _add_video_from_basic_data(entry: Dict, channel: Dict, filesize: Optional[int]) -> None:
        """Add video to database using basic entry data (fallback)."""
        video_id = entry.get("id", "")
        title = entry.get("title", "Unknown Title")
        channel_id = channel.get("channel_id")

        add_video(video_id, title, channel_id, filesize)