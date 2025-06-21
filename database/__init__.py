from database.base import init_database as _init_database_base
from database.config import init_default_config

# Import legacy item functions
from database.items import (
    get_all_items,
    add_item,
    remove_item,
    get_item_by_url,
    update_item,
    item_exists
)

# Import config functions
from database.config import (
    get_config,
    get_parameters,
    set_parameters,
    get_config_value,
    set_config_value
)

# Import new channel functions
from database.channels import (
    get_all_channels,
    add_channel,
    get_channel_by_id,
    channel_exists
)

# Import new video functions
from database.videos import (
    get_all_videos,
    get_videos_by_channel,
    add_video,
    get_video_by_id,
    video_exists
)


def init_database():
    """Initialize database and default configuration."""
    _init_database_base()
    init_default_config()