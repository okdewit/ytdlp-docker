import json

from flask import Flask, render_template, request
from apscheduler.schedulers.background import BackgroundScheduler
from urllib.parse import unquote
from enrich import enrich_item
from item_processing import process_item
from util import logger

app = Flask(__name__)
scheduler = BackgroundScheduler()
scheduler.start()

CONFIG_FILE = "config/config.json"

def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)


def scheduled_task():
    config = load_config()
    parameters = config.get("options", {}).get("parameters", "")
    for item in config.get("items", []):
        process_item(item, parameters)


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
    item_url = request.form.get("item")
    config = load_config()

    logger.info('adding item ' + item_url)

    if item_url and not any(i["url"] == item_url for i in config["items"]):
        new_item = {"url": item_url}
        if enrich_item(new_item):
            config["items"].append(new_item)
            save_config(config)

    return render_template("_item_list.html", items=config["items"])


@app.route("/remove/<path:item>", methods=["DELETE"])
def remove_item(item):
    config = load_config()
    decoded_url = unquote(item)
    config["items"] = [i for i in config["items"] if i["url"] != decoded_url]
    save_config(config)
    return render_template("_item_list.html", items=config["items"])


@app.route("/set-parameters", methods=["POST"])
def set_parameters():
    config = load_config()
    new_params = request.form.get("parameters", "")
    config["options"]["parameters"] = new_params
    save_config(config)
    return "", 204  # No content, because we're not swapping any HTML


@app.route("/update/<path:url>", methods=["POST"])
def update_item(url):
    config = load_config()
    decoded_url = unquote(url)
    item = next((i for i in config["items"] if i["url"] == decoded_url), None)
    if not item:
        return "Item not found", 404
    parameters = config.get("options", {}).get("parameters", "")
    process_item(item, parameters)
    return render_template("_item_list.html", items=config["items"])


scheduler.add_job(scheduled_task, "interval", minutes=120)

if __name__ == "__main__":
    app.run(host="0.0.0.0")
