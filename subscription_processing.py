import subprocess, shlex


def process_subscription(subscription, parameters):
    """Process a subscription based on its sync_scope."""
    url = subscription['url']
    sync_scope = subscription.get('sync_scope', 'single_video')
    channel_name = subscription.get('channel', 'Unknown')

    subprocess.run(["echo", f"Processing {channel_name} ({url}) - scope: {sync_scope}"])

    # Build command based on sync_scope
    cmd = ["./yt-dlp"] + shlex.split(parameters)

    # Add scope-specific parameters
    if sync_scope == 'single_video':
        # Download only the specific video
        cmd.append(url)
    elif sync_scope == 'full_channel':
        # Download all videos from the channel
        if subscription.get('channel_id'):
            cmd.extend(['--download-archive', 'data/downloaded.txt'])
            cmd.append(f"https://www.youtube.com/channel/{subscription['channel_id']}/videos")
        else:
            cmd.append(url)  # Fallback to original URL
    elif sync_scope == 'playlist':
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
    subprocess.run(["echo", f"Done with {channel_name} - scope: {sync_scope}"])
    return result