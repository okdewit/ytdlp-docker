# Import all database initialization and main functions
from database.base import init_database as _init_database_base
from database.config import init_default_config

# Import all item functions
from database.items import (
    get_all_items,
    add_item,
    remove_item,
    get_item_by_url,
    update_item,
    item_exists
)

# Import all config functions
from database.config import (
    get_config,
    get_parameters,
    set_parameters,
    get_config_value,
    set_config_value
)


def init_database():
    """Initialize database and default configuration."""
    _init_database_base()
    init_default_config()