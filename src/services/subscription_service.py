"""
Subscription Service - Orchestrates subscription enrichment.
Responsible for coordinating metadata, channel, and video operations.
"""
from typing import Dict, Optional
from util import logger
from database import add_channel, add_video


class SubscriptionService:
    """Service for orchestrating subscription enrichment operations."""

    def __init__(self, metadata_service, thumbnail_service, video_discovery_service):
        self.metadata_service = metadata_service
        self.thumbnail_service = thumbnail_service
        self.video_discovery_service = video_discovery_service

    def enrich_subscription(self, subscription: Dict) -> bool:
        """
        Main orchestration function - enriches a subscription with metadata.

        Args:
            subscription: Dictionary containing subscription data

        Returns:
            True if enrichment succeeded, False otherwise
        """
        url = subscription["url"]
        logger.info(f'Starting enrichment for subscription: {url}')

        # Step 1: Get metadata
        data = self.metadata_service.fetch_url_metadata(url)
        if not data:
            logger.error(f"Could not get info for {url}")
            return False

        # Step 2: Determine and set subscription type
        subscription_type = self.metadata_service.determine_subscription_type(data)
        if subscription_type == "unknown":
            logger.error(f"Could not determine type for {url}")
            return False

        subscription["type"] = subscription_type

        # Step 3: Extract and set channel information
        channel_info = self.metadata_service.extract_channel_info(data)
        subscription.update(channel_info)

        # Step 4: Handle database operations for channel
        self._handle_channel_operations(subscription)

        # Step 5: Handle type-specific operations
        self._handle_type_specific_operations(subscription, data, subscription_type)

        logger.info(f'Successfully enriched subscription {url} - type: {subscription_type}')
        return True

    def _handle_channel_operations(self, subscription: Dict) -> None:
        """Handle database operations and thumbnail download for the channel."""
        channel_id = subscription.get("channel_id")
        channel_name = subscription.get("channel")

        if not channel_id:
            return

        # Add/update channel in database
        add_channel(channel_id, channel_name)

        # Download channel thumbnail
        if channel_name:
            poster_path = self.thumbnail_service.download_channel_thumbnail(channel_id, channel_name)
            if poster_path:
                subscription["poster_path"] = poster_path

    def _handle_type_specific_operations(self, subscription: Dict, data: Dict, subscription_type: str) -> None:
        """Handle operations specific to subscription type (video, channel, playlist)."""
        if subscription_type == "video":
            self._handle_video_subscription(subscription, data)
        elif subscription_type == "channel":
            self._handle_channel_subscription(subscription)
        elif subscription_type == "playlist":
            logger.info(f'Playlist subscription detected: {subscription.get("channel")}')

    def _handle_video_subscription(self, subscription: Dict, data: Dict) -> None:
        """Handle video-specific operations: add to database and download thumbnail."""
        video_id = data.get("id", "")
        if not video_id:
            return

        title = data.get("title", "Unknown Title")
        channel_id = subscription.get("channel_id")
        channel_name = subscription.get("channel")

        expected_filename = self.video_discovery_service.generate_video_filename(
            data, title, video_id, channel_name
        )

        add_video(video_id, title, channel_id, expected_filename)
        logger.info(f'Added video to database: {title} ({video_id})')

        # Download thumbnail for single video's channel
        if channel_id and channel_name:
            self.thumbnail_service.download_channel_thumbnail(channel_id, channel_name)

    def _handle_channel_subscription(self, subscription: Dict) -> None:
        """Handle channel-specific operations: populate all videos."""
        channel_name = subscription.get("channel")
        channel_id = subscription.get("channel_id")

        logger.info(f'Channel subscription detected, populating videos for: {channel_name}')
        if channel_id:
            self.video_discovery_service.populate_videos_from_channel(channel_id)