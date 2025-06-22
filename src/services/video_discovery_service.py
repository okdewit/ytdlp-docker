"""
Video Discovery Service - Enhanced to use yt-dlp's actual filename generation and filesize.
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

            # Get current parameters for filename generation
            parameters = get_parameters()

            for i, entry in enumerate(entries):
                self._process_channel_video_entry(entry, i + 1, len(entries), channel, parameters)

            logger.info(f'Populated {len(entries)} videos for channel: {channel["name"]}')
            return True

        except Exception as e:
            logger.error(f"Error populating videos for channel {channel_id}: {e}")
            return False

    def generate_video_filename_with_ytdlp(self, video_id: str, title: str, channel_name: str) -> str:
        """
        Generate expected filename using yt-dlp's actual filename generation.

        Args:
            video_id: YouTube video ID
            title: Video title (fallback)
            channel_name: Channel name (fallback)

        Returns:
            Expected filename string
        """
        # Get current parameters (full string)
        parameters = get_parameters()

        if parameters:
            # Try to get filename from yt-dlp using full parameters
            ytdlp_filename = self.metadata_service.get_ytdlp_filename(video_id, parameters)
            if ytdlp_filename:
                return ytdlp_filename

        # Fallback to our old method
        return self._generate_fallback_filename(title, video_id, channel_name)

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

            # Generate expected filename
            title = metadata.get("title", "Unknown Title")
            channel_name = metadata.get("uploader", "Unknown")
            expected_filename = self.generate_video_filename_with_ytdlp(video_id, title, channel_name)

            # Add to database with filesize
            video_data = add_video(
                video_id=video_id,
                title=title,
                channel_id=channel_id,
                expected_filename=expected_filename,
                filesize=metadata.get("filesize")
            )

            logger.info(f"Processed video with filesize: {title} - {metadata.get('filesize', 'unknown')} bytes")
            return video_data

        except Exception as e:
            logger.error(f"Error processing video {video_id}: {e}")
            return None

    def _extract_output_template(self, parameters: str) -> Optional[str]:
        """
        Extract the -o parameter from the full parameters string.

        Args:
            parameters: Full yt-dlp parameters string

        Returns:
            Output template string or None if not found
        """
        import shlex

        try:
            # Parse the parameters string
            args = shlex.split(parameters)

            # Find the -o parameter
            for i, arg in enumerate(args):
                if arg == "-o" and i + 1 < len(args):
                    return args[i + 1]
                elif arg.startswith("-o="):
                    return arg[3:]  # Remove "-o=" prefix

        except Exception as e:
            logger.warning(f"Failed to parse parameters: {e}")

        return None

    def _process_channel_video_entry(self, entry: Dict, current_index: int, total_count: int,
                                   channel: Dict, parameters: str) -> None:
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
            self._add_video_from_detailed_data(video_data, channel, parameters, filesize)
        else:
            self._add_video_from_basic_data(entry, channel, parameters, filesize)

    def _add_video_from_detailed_data(self, video_data: Dict, channel: Dict, parameters: str, filesize: Optional[int]) -> None:
        """Add video to database using detailed video data."""
        video_id = video_data.get("id", "")
        title = video_data.get("title", "Unknown Title")
        channel_id = channel.get("channel_id")
        channel_name = channel.get("name")

        # Try to get yt-dlp's actual filename using full parameters
        expected_filename = None
        if parameters:
            expected_filename = self.metadata_service.get_ytdlp_filename(video_id, parameters)

        # Fallback if yt-dlp filename generation fails
        if not expected_filename:
            expected_filename = self._generate_fallback_filename(title, video_id, channel_name)

        add_video(video_id, title, channel_id, expected_filename, filesize)

    def _add_video_from_basic_data(self, entry: Dict, channel: Dict, parameters: str, filesize: Optional[int]) -> None:
        """Add video to database using basic entry data (fallback)."""
        video_id = entry.get("id", "")
        title = entry.get("title", "Unknown Title")
        channel_id = channel.get("channel_id")
        channel_name = channel.get("name")

        # Try to get yt-dlp's actual filename using full parameters
        expected_filename = None
        if parameters:
            expected_filename = self.metadata_service.get_ytdlp_filename(video_id, parameters)

        # Fallback if yt-dlp filename generation fails
        if not expected_filename:
            expected_filename = self._generate_fallback_filename(title, video_id, channel_name)

        add_video(video_id, title, channel_id, expected_filename, filesize)

    def _generate_fallback_filename(self, title: str, video_id: str, channel_name: str) -> str:
        """Generate filename using fallback method (our old logic)."""
        uploader = self._clean_filename_part(channel_name) if channel_name else "Unknown"
        clean_title = self._clean_filename_part(title)
        return f"{uploader}/Unknown-Date - {clean_title} [{video_id}].mp4"

    @staticmethod
    def _clean_filename_part(name: str) -> str:
        """Clean a string to be safe for use in filenames."""
        return name.replace("/", "-").replace("\\", "-").strip()

    # Keep the old method for backward compatibility
    def generate_video_filename(self, data: Dict, title: str, video_id: str, channel_name: str) -> str:
        """Legacy method - use generate_video_filename_with_ytdlp instead."""
        logger.warning("Using legacy generate_video_filename method")
        return self._generate_fallback_filename(title, video_id, channel_name)