from database.base import init_database as _init_database_base
from database.config import init_default_config

# Import subscription functions (renamed from items)
from database.subscriptions import (
    get_all_subscriptions,
    add_subscription,
    remove_subscription,
    get_subscription_by_url,
    update_subscription,
    subscription_exists
)

# Import config functions
from database.config import (
    get_config,
    get_parameters,
    set_parameters,
    get_config_value,
    set_config_value
)

# Import channel functions
from database.channels import (
    get_all_channels,
    add_channel,
    get_channel_by_id,
    channel_exists
)

# Import video functions
from database.videos import (
    get_all_videos,
    get_videos_by_channel,
    get_channel_video_stats,
    add_video,
    update_video_filesize,
    get_video_by_id,
    video_exists,
    format_filesize
)


def init_database():
    """Initialize database and default configuration."""
    _init_database_base()
    init_default_config()