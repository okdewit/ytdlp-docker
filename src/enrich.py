"""
enrich.py - Refactored to use service architecture while maintaining backward compatibility.
This file now acts as a facade for the new service-based architecture.
"""
from services.metadata_service import MetadataService
from services.thumbnail_service import ThumbnailService
from services.video_discovery_service import VideoDiscoveryService
from services.subscription_service import SubscriptionService

# Initialize services (using dependency injection pattern)
metadata_service = MetadataService()
thumbnail_service = ThumbnailService()
video_discovery_service = VideoDiscoveryService(metadata_service)
subscription_service = SubscriptionService(
    metadata_service,
    thumbnail_service,
    video_discovery_service
)


def enrich_subscription(subscription):
    """
    Main enrichment function - now delegates to SubscriptionService.
    Maintains backward compatibility with existing code.

    Args:
        subscription: Dictionary containing subscription data

    Returns:
        True if enrichment succeeded, False otherwise
    """
    return subscription_service.enrich_subscription(subscription)


def populate_videos_from_channel(channel_id, limit=50):
    """
    Populate videos from channel - delegates to VideoDiscoveryService.
    Maintains backward compatibility.

    Args:
        channel_id: YouTube channel ID
        limit: Maximum number of videos to process

    Returns:
        True if successful, False otherwise
    """
    return video_discovery_service.populate_videos_from_channel(channel_id, limit)


# Legacy function aliases for backward compatibility
def get_ytdlp_info(url):
    """Legacy alias for fetch_url_metadata."""
    return metadata_service.fetch_url_metadata(url)


def determine_subscription_type(data):
    """Legacy alias for determine_subscription_type."""
    return metadata_service.determine_subscription_type(data)


def download_channel_thumbnail(channel_id, uploader_name):
    """Legacy alias for download_channel_thumbnail."""
    return thumbnail_service.download_channel_thumbnail(channel_id, uploader_name)