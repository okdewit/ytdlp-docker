from flask import Flask, render_template, request, send_from_directory
from flask_socketio import SocketIO, emit
from apscheduler.schedulers.background import BackgroundScheduler
from urllib.parse import unquote
import os
from enrich import enrich_subscription
from subscription_processing import process_subscription
from util import logger
from database import (
    get_config, get_all_subscriptions, get_subscription_by_url, add_subscription,
    remove_subscription, get_parameters, set_parameters, update_subscription,
    init_database, get_channel_video_stats
)
# Import WebSocket utilities
from websocket_events import init_websocket_events, emit_subscription_event

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Change this in production
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize WebSocket events
init_websocket_events(socketio)

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

    # Enrich subscriptions with channel statistics
    for subscription in subscriptions:
        channel_id = subscription.get('channel_id')
        if channel_id:
            stats = get_channel_video_stats(channel_id)
            subscription['stats'] = stats
        else:
            # Default stats for subscriptions without channel_id
            subscription['stats'] = {
                'total_count': 0,
                'downloaded_count': 0,
                'pending_count': 0,
                'downloaded_size_human': '0 B',
                'total_size_human': '0 B'
            }

    return render_template("_subscription_list.html", subscriptions=subscriptions)

@app.route("/items")
def items():
    """Legacy route for backward compatibility."""
    return subscriptions()


@app.route("/static/data/<path:filename>")
def serve_data_files(filename):
    """Serve files from the data directory."""
    data_dir = os.path.join(os.getcwd(), "data")
    return send_from_directory(data_dir, filename)


@app.route("/add", methods=["POST"])
def add_subscription_route():
    subscription_url = request.form.get("item")  # Keep form field name for template compatibility

    logger.info('adding subscription ' + subscription_url)

    if subscription_url:
        # Check if subscription already exists
        existing_subscription = get_subscription_by_url(subscription_url)
        if not existing_subscription:
            # Create initial subscription entry with minimal data
            new_subscription = {
                "url": subscription_url,
                "type": "",
                "channel": "Processing...",
                "channel_id": "",
                "_enriching": True  # Flag to show this is being processed
            }

            # Add placeholder to database immediately
            add_subscription(new_subscription)

            # Emit initial event
            emit_subscription_event("started", {
                "url": subscription_url,
                "message": "Starting subscription enrichment..."
            })

            # Get current subscriptions including the new placeholder
            subscriptions = get_all_subscriptions()

            # Mark the new one as enriching and add stats
            for subscription in subscriptions:
                if subscription['url'] == subscription_url:
                    subscription['_enriching'] = True

                # Add default stats for display
                channel_id = subscription.get('channel_id')
                if channel_id:
                    stats = get_channel_video_stats(channel_id)
                    subscription['stats'] = stats
                else:
                    subscription['stats'] = {
                        'total_count': 0,
                        'downloaded_count': 0,
                        'pending_count': 0,
                        'downloaded_size_human': '0 B',
                        'total_size_human': '0 B'
                    }

            # Return the updated list immediately (with placeholder)
            response_html = render_template("_subscription_list.html", subscriptions=subscriptions)

            # Start enrichment process in background (this will emit more events)
            # We need to do this after returning the response, so let's use a background task
            from threading import Thread
            def enrich_in_background():
                if enrich_subscription(new_subscription):
                    # Update the database with enriched data
                    update_subscription(new_subscription)

                    emit_subscription_event("complete", {
                        "url": subscription_url,
                        "message": "Subscription enrichment complete!",
                        "subscription": new_subscription
                    })
                else:
                    emit_subscription_event("error", {
                        "url": subscription_url,
                        "message": "Failed to enrich subscription"
                    })

            # Start background enrichment
            thread = Thread(target=enrich_in_background)
            thread.daemon = True
            thread.start()

            return response_html

    # If no URL or subscription exists, just return current list
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

    # Emit start event
    emit_subscription_event("update_started", {
        "url": decoded_url,
        "message": f"Starting update for {subscription.get('channel', 'subscription')}..."
    })

    parameters = get_parameters()
    process_subscription(subscription, parameters)
    update_subscription(subscription)

    # Emit complete event
    emit_subscription_event("update_complete", {
        "url": decoded_url,
        "message": f"Update complete for {subscription.get('channel', 'subscription')}"
    })

    subscriptions = get_all_subscriptions()
    return render_template("_subscription_list.html", subscriptions=subscriptions)

@app.route("/videos/<channel_id>")
def get_videos_for_channel(channel_id):
    """Route for HTMX to load videos for a specific channel."""
    from database import get_videos_by_channel

    if channel_id == "unknown" or not channel_id:
        videos = []
    else:
        videos = get_videos_by_channel(channel_id)

    return render_template("_video_list.html", videos=videos)


# WebSocket event handlers
@socketio.on('connect')
def handle_connect():
    """Handle new WebSocket connection."""
    logger.info('Client connected to WebSocket')
    emit('connected', {'message': 'Connected to YTDLP manager'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection."""
    logger.info('Client disconnected from WebSocket')


# Initialize database on startup
init_database()

scheduler.add_job(scheduled_task, "interval", minutes=120)

if __name__ == "__main__":
    # Use socketio.run instead of app.run for WebSocket support
    # allow_unsafe_werkzeug=True is needed for development/testing
    socketio.run(app, host="0.0.0.0", debug=True, allow_unsafe_werkzeug=True)