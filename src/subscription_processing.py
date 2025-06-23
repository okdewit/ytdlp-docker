import subprocess, shlex
from util import YTDLP_BINARY, logger


def process_subscription(subscription, parameters):
    """Process a subscription based on its type."""
    url = subscription['url']
    subscription_type = subscription.get('type', 'video')
    channel_name = subscription.get('channel', 'Unknown')

    logger.info(f"Processing {channel_name} ({url}) - type: {subscription_type}")

    # Build base command with user parameters
    cmd = [YTDLP_BINARY] + shlex.split(parameters)
    cmd.append(url)

    logger.info(f"Executing command: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3600  # 1 hour timeout for large downloads
        )

        # Log the output for visibility
        if result.stdout:
            logger.info(f"yt-dlp stdout for {channel_name}:")
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    logger.info(f"  {line}")

        if result.stderr:
            logger.warning(f"yt-dlp stderr for {channel_name}:")
            for line in result.stderr.strip().split('\n'):
                if line.strip():
                    logger.warning(f"  {line}")

        if result.returncode == 0:
            logger.info(f"Successfully completed processing {channel_name}")
        else:
            logger.error(f"yt-dlp failed for {channel_name} with return code {result.returncode}")

        return result

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout processing {channel_name} - operation took longer than 1 hour")
        return None
    except Exception as e:
        logger.error(f"Unexpected error processing {channel_name}: {e}")
        return None