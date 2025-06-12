import subprocess, shlex


def process_item(item, parameters):
    subprocess.run(["echo", f"Processing {item['channel']} ({item['url']})"])
    cmd = ["./yt-dlp"] + shlex.split(parameters) + [item["url"]]
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    subprocess.run(["echo", f"Done with {item['channel']}"])
    return result