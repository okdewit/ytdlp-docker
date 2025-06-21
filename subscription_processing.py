import subprocess, shlex


def process_subscription(subscription, parameters):
    """Process a subscription based on its type."""
    url = subscription['url']
    subscription_type = subscription.get('type', 'video')
    channel_name = subscription.get('channel', 'Unknown')

    subprocess.run(["echo", f"Processing {channel_name} ({url}) - type: {subscription_type}"])

    # Build command based on subscription type
    cmd = ["./yt-dlp"] + shlex.split(parameters)

    # Add type-specific parameters
    if subscription_type == 'video':
        # Download only the specific video
        cmd.append(url)
    elif subscription_type == 'channel':
        # Download all videos from the channel
        if subscription.get('channel_id'):
            cmd.extend(['--download-archive', 'data/downloaded.txt'])
            cmd.append(f"https://www.youtube.com/channel/{subscription['channel_id']}/videos")
        else:
            cmd.append(url)  # Fallback to original URL
    elif subscription_type == 'playlist':
        # Download the specific playlist
        cmd.extend(['--download-archive', 'data/downloaded.txt'])
        cmd.append(url)
    else:
        # Default behavior
        cmd.append(url)

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    subprocess.run(["echo", f"Done with {channel_name} - type: {subscription_type}"])
    return result