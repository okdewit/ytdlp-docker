from flask import Flask, render_template, request
from apscheduler.schedulers.background import BackgroundScheduler
from urllib.parse import unquote
from enrich import enrich_subscription
from subscription_processing import process_subscription
from util import logger
from database import (
    get_config, get_all_subscriptions, get_subscription_by_url, add_subscription,
    remove_subscription, get_parameters, set_parameters, update_subscription,
    init_database
)

app = Flask(__name__)
scheduler = BackgroundScheduler()
scheduler.start()


def scheduled_task():
    """Background task that processes all subscriptions."""
    parameters = get_parameters()
    subscriptions = get_all_subscriptions()

    for subscription in subscriptions:
        process_subscription(subscription, parameters)
        # Update the subscription in database after processing
        update_subscription(subscription)


@app.route("/")
def index():
    config = get_config()
    return render_template("index.html", config=config)


@app.route("/subscriptions")
def subscriptions():
    """Route for HTMX to load subscription list."""
    subscriptions = get_all_subscriptions()
    return render_template("_subscription_list.html", subscriptions=subscriptions)

@app.route("/items")
def items():
    """Legacy route for backward compatibility."""
    return subscriptions()


@app.route("/add", methods=["POST"])
def add_subscription_route():
    subscription_url = request.form.get("item")  # Keep form field name for template compatibility

    logger.info('adding subscription ' + subscription_url)

    if subscription_url:
        # Check if subscription already exists
        existing_subscription = get_subscription_by_url(subscription_url)
        if not existing_subscription:
            new_subscription = {"url": subscription_url}
            if enrich_subscription(new_subscription):
                add_subscription(new_subscription)

    subscriptions = get_all_subscriptions()
    return render_template("_subscription_list.html", subscriptions=subscriptions)


@app.route("/remove/<path:item>", methods=["DELETE"])
def remove_subscription_route(item):
    decoded_url = unquote(item)
    remove_subscription(decoded_url)
    subscriptions = get_all_subscriptions()
    return render_template("_subscription_list.html", subscriptions=subscriptions)


@app.route("/set-parameters", methods=["POST"])
def set_parameters_route():
    new_params = request.form.get("parameters", "")
    set_parameters(new_params)
    return "", 204  # No content, because we're not swapping any HTML


@app.route("/update/<path:url>", methods=["POST"])
def update_subscription_route(url):
    decoded_url = unquote(url)
    subscription = get_subscription_by_url(decoded_url)
    if not subscription:
        return "Subscription not found", 404

    parameters = get_parameters()
    process_subscription(subscription, parameters)
    update_subscription(subscription)

    subscriptions = get_all_subscriptions()
    return render_template("_subscription_list.html", subscriptions=subscriptions)


# Initialize database on startup
init_database()

scheduler.add_job(scheduled_task, "interval", minutes=120)

if __name__ == "__main__":
    app.run(host="0.0.0.0")