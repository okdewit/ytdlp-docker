import subprocess
import json

from util import logger


def enrich_item(item):
    """
    Enrich an item dict by adding metadata from yt-dlp.
    Adds channel name and type ('video', 'playlist', or 'channel').
    Returns True if enrichment succeeded, False otherwise.
    """
    try:
        logger.info('starting enrichment for item ' + item["url"])

        result = subprocess.run(
            ["./yt-dlp", "--flat-playlist", "-J", item["url"]],
            capture_output=True,
            text=True,
            check=True
        )
        metadata = json.loads(result.stdout)

        # Channel name
        item["channel"] = metadata.get("channel", "Unknown Channel")

        logger.info('enrichting item ' + item["url"] + ' with channel name ' + item["channel"])

        # Determine type
        _type = metadata.get("_type")
        extractor = metadata.get("extractor")

        logger.info('found type ' + _type + ', ' + extractor + ' for ' + item["url"])

        if not _type or _type == 'video':
            item["type"] = "video"
        elif extractor == "youtube:playlist":
            item["type"] = "playlist"
        elif extractor in ("youtube:channel", "youtube:user"):
            item["type"] = "channel"
        else:
            item["type"] = "unknown"

        return True

    except subprocess.CalledProcessError as e:
        print(f"yt-dlp failed for {item['url']}: {e.stderr}")
    except json.JSONDecodeError as e:
        print(f"Invalid JSON for {item['url']}: {e}")

    return False