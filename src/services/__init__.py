"""
Services package - Contains business logic services for the ytdlp application.

This package separates concerns into focused service classes:
- MetadataService: Handles ytdlp interaction and JSON parsing
- ThumbnailService: Manages channel avatar/thumbnail downloading
- VideoDiscoveryService: Handles channel video population
- SubscriptionService: Orchestrates subscription enrichment
"""

from .metadata_service import MetadataService
from .thumbnail_service import ThumbnailService
from .video_discovery_service import VideoDiscoveryService
from .subscription_service import SubscriptionService

__all__ = [
    'MetadataService',
    'ThumbnailService',
    'VideoDiscoveryService',
    'SubscriptionService'
]