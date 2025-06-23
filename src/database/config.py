from datetime import datetime
from pony.orm import PrimaryKey, Optional, Required, db_session
from database.base import db
from util import logger


class Config(db.Entity):
    """Config entity for storing key-value configuration pairs."""
    _table_ = 'config'
    key = PrimaryKey(str)
    value = Optional(str)
    updated_at = Required(datetime, default=lambda: datetime.now())

# Default yt-dlp parameters
DEFAULT_PARAMETERS = ('-f "bv[vcodec^=av01][height<=1080]+ba/bv[ext=mp4][height<=1080]+ba/b[height<=1080]" '
                     +'--merge-output-format mp4 '
                     +'-o "%(uploader)s/%(upload_date>%Y-%m-%d)s - %(title)s [%(id)s].%(ext)s" '
                     +'--write-subs --sub-langs "en.*" '
                     +'--download-archive data/downloaded.txt '
                     +'--sponsorblock-mark all '
                     +'--sponsorblock-remove sponsor '
                     +'--embed-metadata '
                     +'--embed-thumbnail '
                     +'--write-info-json '
                     +'--write-desktop-link '
                     +'--write-description '
                     +'--write-thumbnail '
                     +'--convert-thumbnail jpg '
                     +'-P "data"')


def init_default_config():
    """Initialize default configuration values."""
    with db_session:
        if not Config.exists(key='parameters'):
            Config(key='parameters', value=DEFAULT_PARAMETERS)
            logger.info("Database initialized with default parameters")


@db_session
def get_config():
    """Get configuration as a dictionary."""
    params_config = Config.get(key='parameters')
    parameters = params_config.value if params_config else ""

    return {
        "options": {"parameters": parameters}
    }


@db_session
def get_parameters():
    """Get the current parameters from config."""
    config = Config.get(key='parameters')
    return config.value if config else ""


@db_session
def set_parameters(parameters):
    """Set parameters in the database."""
    try:
        config = Config.get(key='parameters')
        if config:
            config.value = parameters
            config.updated_at = datetime.now()
        else:
            Config(key='parameters', value=parameters)
        return True
    except Exception as e:
        logger.error(f"Error setting parameters: {e}")
        return False


@db_session
def get_config_value(key, default=None):
    """Get a specific config value by key."""
    config = Config.get(key=key)
    return config.value if config else default


@db_session
def set_config_value(key, value):
    """Set a specific config value."""
    try:
        config = Config.get(key=key)
        if config:
            config.value = value
            config.updated_at = datetime.now()
        else:
            Config(key=key, value=value)
        return True
    except Exception as e:
        logger.error(f"Error setting config value: {e}")
        return False