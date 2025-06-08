from flask import Flask, render_template, request, redirect
from apscheduler.schedulers.background import BackgroundScheduler
import json, subprocess, shlex

app = Flask(__name__)
scheduler = BackgroundScheduler()
scheduler.start()

CONFIG_FILE = "config.json"

def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f)

def scheduled_task():
    config = load_config()
    items = config.get("items", [])
    parameters = config.get("options", {}).get("parameters", "")
    for item in items:
        subprocess.run(["echo", f"Processing {item}"])
        cmd = ["./yt-dlp"] + shlex.split(parameters) + [item]
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        subprocess.run(["echo", f"Done with {item}"])

@app.route("/")
def index():
    config = load_config()
    return render_template("index.html", config=config)

@app.route("/items")
def items():
    config = load_config()
    return render_template("_item_list.html", items=config["items"])

@app.route("/add", methods=["POST"])
def add_item():
    item = request.form.get("item")
    config = load_config()
    if item and item not in config["items"]:
        config["items"].append(item)
        save_config(config)
    return render_template("_item_list.html", items=config["items"])

@app.route("/remove/<item>", methods=["DELETE"])
def remove_item(item):
    config = load_config()
    config["items"] = [i for i in config["items"] if i != item]
    save_config(config)
    return render_template("_item_list.html", items=config["items"])

@app.route("/set-parameters", methods=["POST"])
def set_parameters():
    config = load_config()
    new_params = request.form.get("parameters", "")
    config["options"]["parameters"] = new_params
    save_config(config)
    return "", 204  # No content, because we're not swapping any HTML

scheduler.add_job(scheduled_task, "interval", minutes=60)

if __name__ == "__main__":
    app.run(host="0.0.0.0")