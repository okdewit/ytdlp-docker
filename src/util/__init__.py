import logging
import sys
import os

# Configuration for yt-dlp binary location
YTDLP_BINARY = os.getenv('YTDLP_BINARY', '/app/yt-dlp')

# Configure root logger
logging.basicConfig(
    level=logging.INFO,  # or DEBUG for more verbosity
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)