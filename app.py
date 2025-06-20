from flask import Flask, render_template, request
from apscheduler.schedulers.background import BackgroundScheduler
from urllib.parse import unquote
from enrich import enrich_item
from item_processing import process_item
from util import logger
import database

app = Flask(__name__)
scheduler = BackgroundScheduler()
scheduler.start()


def scheduled_task():
    """Background task that processes all items."""
    parameters = database.get_parameters()
    items = database.get_all_items()
    
    for item in items:
        process_item(item, parameters)
        # Update the item in database after processing
        database.update_item(item)


@app.route("/")
def index():
    config = database.get_config()
    items = database.get_all_items()
    return render_template("index.html", config=config, items=items)


@app.route("/items")
def items():
    items = database.get_all_items()
    return render_template("_item_list.html", items=items)


@app.route("/add", methods=["POST"])
def add_item():
    item_url = request.form.get("item")
    
    logger.info('adding item ' + item_url)
    
    if item_url:
        # Check if item already exists
        existing_item = database.get_item_by_url(item_url)
        if not existing_item:
            new_item = {"url": item_url}
            if enrich_item(new_item):
                database.add_item(new_item)
    
    items = database.get_all_items()
    return render_template("_item_list.html", items=items)


@app.route("/remove/<path:item>", methods=["DELETE"])
def remove_item(item):
    decoded_url = unquote(item)
    database.remove_item(decoded_url)
    items = database.get_all_items()
    return render_template("_item_list.html", items=items)


@app.route("/set-parameters", methods=["POST"])
def set_parameters():
    new_params = request.form.get("parameters", "")
    database.set_parameters(new_params)
    return "", 204  # No content, because we're not swapping any HTML


@app.route("/update/<path:url>", methods=["POST"])
def update_item(url):
    decoded_url = unquote(url)
    item = database.get_item_by_url(decoded_url)
    if not item:
        return "Item not found", 404
    
    parameters = database.get_parameters()
    process_item(item, parameters)
    database.update_item(item)
    
    items = database.get_all_items()
    return render_template("_item_list.html", items=items)


# Initialize database on startup
database.init_database()

scheduler.add_job(scheduled_task, "interval", minutes=120)

if __name__ == "__main__":
    app.run(host="0.0.0.0")