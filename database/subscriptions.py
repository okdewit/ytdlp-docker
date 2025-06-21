from datetime import datetime
from pony.orm import *
from database.base import db
from util import logger


class Subscription(db.Entity):
    """Subscription entity representing a user's subscription to a video, playlist, or channel URL."""
    _table_ = 'subscriptions'
    id = PrimaryKey(int, auto=True)
    url = Required(str, unique=True)
    subscription_type = Optional(str, column='type')  # video, playlist, or channel
    created_at = Required(datetime, default=lambda: datetime.now())
    updated_at = Required(datetime, default=lambda: datetime.now())

    # Foreign key to channel (when discovered)
    channel = Optional('Channel')


def _subscription_to_dict(subscription):
    """Convert a Subscription entity to a dictionary."""
    return {
        "url": subscription.url,
        "type": subscription.subscription_type or "",
        "channel": subscription.channel.name if subscription.channel else "",
        "channel_id": subscription.channel.channel_id if subscription.channel else ""
    }


@db_session
def get_all_subscriptions():
    """Get all subscriptions from database."""
    return [_subscription_to_dict(subscription) for subscription in
            select(s for s in Subscription).order_by(desc(Subscription.created_at))]


@db_session
def add_subscription(subscription_data):
    """Add a subscription to the database."""
    try:
        # Get channel if provided
        channel = None
        if subscription_data.get("channel_id"):
            from database.channels import Channel
            channel = Channel.get(channel_id=subscription_data["channel_id"])

        Subscription(
            url=subscription_data["url"],
            subscription_type=subscription_data.get("type", ""),
            channel=channel
        )
        return True
    except Exception as e:
        logger.error(f"Error adding subscription: {e}")
        return False


@db_session
def remove_subscription(url):
    """Remove a subscription from the database."""
    try:
        subscription = Subscription.get(url=url)
        if subscription:
            subscription.delete()
            return True
        return False
    except Exception as e:
        logger.error(f"Error removing subscription: {e}")
        return False


@db_session
def get_subscription_by_url(url):
    """Get a specific subscription by URL."""
    subscription = Subscription.get(url=url)
    if subscription:
        return _subscription_to_dict(subscription)
    return None


@db_session
def update_subscription(subscription_data):
    """Update a subscription in the database."""
    try:
        subscription = Subscription.get(url=subscription_data["url"])
        if subscription:
            subscription.subscription_type = subscription_data.get("type", subscription.subscription_type)
            subscription.updated_at = datetime.now()

            # Update channel relationship if provided
            if subscription_data.get("channel_id"):
                from database.channels import Channel
                channel = Channel.get(channel_id=subscription_data["channel_id"])
                subscription.channel = channel

            return True
        return False
    except Exception as e:
        logger.error(f"Error updating subscription: {e}")
        return False


@db_session
def subscription_exists(url):
    """Check if a subscription exists by URL."""
    return Subscription.exists(url=url)