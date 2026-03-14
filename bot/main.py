"""Entry point for the Home Telegram Bot."""

import logging
import sys

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from bot.config import BOT_TOKEN, DB_PATH
from bot.database import Database
from bot.handlers import (
    cmd_approve,
    cmd_deny,
    cmd_help,
    cmd_start,
    cmd_stats,
    cmd_users,
    cmd_status,
    handle_message,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def build_application() -> Application:
    """Build and configure the Telegram :class:`Application`."""
    if not BOT_TOKEN:
        logger.error(
            "BOT_TOKEN is not set. Create a .env file or set the environment variable."
        )
        sys.exit(1)

    app = Application.builder().token(BOT_TOKEN).build()

    # Attach the database to bot_data so handlers can access it
    app.bot_data["db"] = Database(DB_PATH)

    # Register command handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("users", cmd_users))
    app.add_handler(CommandHandler("approve", cmd_approve))
    app.add_handler(CommandHandler("deny", cmd_deny))
    app.add_handler(CommandHandler("stats", cmd_stats))

    # Handle plain text messages (link fetching)
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    return app


def main() -> None:
    """Start the bot in long-polling mode."""
    app = build_application()
    logger.info("Starting bot…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
