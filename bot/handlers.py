"""Telegram bot command and message handlers."""

import logging
from typing import Optional

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.config import ADMIN_IDS
from bot.database import Database, STATUS_APPROVED, STATUS_DENIED, STATUS_PENDING
from bot.link_fetcher import fetch_link_info, is_valid_url

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _db(context: ContextTypes.DEFAULT_TYPE) -> Database:
    """Retrieve the :class:`Database` stored in ``context.bot_data``."""
    return context.bot_data["db"]


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def _full_name(update: Update) -> str:
    user = update.effective_user
    if user is None:
        return "Unknown"
    return user.full_name or user.username or str(user.id)


# ──────────────────────────────────────────────────────────────────────────────
# User-facing commands
# ──────────────────────────────────────────────────────────────────────────────


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Register the user and show a welcome message."""
    user = update.effective_user
    if user is None:
        return

    db = _db(context)
    inserted = db.add_user(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name or user.username or str(user.id),
    )

    if inserted:
        await update.message.reply_text(
            "👋 Welcome! Your access request has been sent to the admin.\n"
            "You will be notified once it is reviewed."
        )
        # Notify admins
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=(
                        f"🆕 New access request\n"
                        f"User: {user.full_name} (@{user.username})\n"
                        f"ID: <code>{user.id}</code>\n\n"
                        f"Use /approve {user.id} or /deny {user.id}"
                    ),
                    parse_mode=ParseMode.HTML,
                )
            except Exception as exc:
                logger.warning("Could not notify admin %s: %s", admin_id, exc)
    else:
        row = db.get_user(user.id)
        status = row["status"] if row else STATUS_PENDING
        if status == STATUS_APPROVED:
            await update.message.reply_text(
                "✅ You already have access. Send me any URL and I'll fetch it for you!"
            )
        elif status == STATUS_DENIED:
            await update.message.reply_text(
                "❌ Your access request was denied. Contact the admin for help."
            )
        else:
            await update.message.reply_text(
                "⏳ Your request is still pending. Please wait for admin approval."
            )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show available commands."""
    user = update.effective_user
    if user is None:
        return

    lines = [
        "<b>Home Telegram Bot – Help</b>",
        "",
        "/start – Register and request access",
        "/help  – Show this help message",
        "/status – Check your access status",
    ]
    if _is_admin(user.id):
        lines += [
            "",
            "<b>Admin commands</b>",
            "/users [pending|approved|denied] – List users",
            "/approve &lt;user_id&gt; – Approve a user",
            "/deny &lt;user_id&gt; – Deny a user",
            "/stats – Show user statistics",
        ]
    await update.message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.HTML
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Let a user check their own approval status."""
    user = update.effective_user
    if user is None:
        return

    db = _db(context)
    row = db.get_user(user.id)
    if row is None:
        await update.message.reply_text(
            "You haven't registered yet. Use /start to request access."
        )
        return

    status_emoji = {
        STATUS_PENDING: "⏳ Pending",
        STATUS_APPROVED: "✅ Approved",
        STATUS_DENIED: "❌ Denied",
    }
    label = status_emoji.get(row["status"], row["status"])
    await update.message.reply_text(f"Your status: {label}")


# ──────────────────────────────────────────────────────────────────────────────
# Admin commands
# ──────────────────────────────────────────────────────────────────────────────


async def cmd_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List users, optionally filtered by status."""
    user = update.effective_user
    if user is None or not _is_admin(user.id):
        await update.message.reply_text("⛔ This command is for admins only.")
        return

    db = _db(context)
    filter_status: Optional[str] = None
    args = context.args or []
    if args:
        arg = args[0].lower()
        if arg in (STATUS_PENDING, STATUS_APPROVED, STATUS_DENIED):
            filter_status = arg
        else:
            await update.message.reply_text(
                "Usage: /users [pending|approved|denied]"
            )
            return

    rows = db.list_users(filter_status)
    if not rows:
        await update.message.reply_text("No users found.")
        return

    status_emoji = {
        STATUS_PENDING: "⏳",
        STATUS_APPROVED: "✅",
        STATUS_DENIED: "❌",
    }
    lines = [f"<b>Users{' (' + filter_status + ')' if filter_status else ''}</b>"]
    for row in rows:
        emoji = status_emoji.get(row["status"], "❓")
        name = row["full_name"] or "—"
        username = f"@{row['username']}" if row["username"] else "—"
        lines.append(
            f"{emoji} <code>{row['user_id']}</code> {name} {username}"
        )
    await update.message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.HTML
    )


async def cmd_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Approve a user: /approve <user_id>"""
    user = update.effective_user
    if user is None or not _is_admin(user.id):
        await update.message.reply_text("⛔ This command is for admins only.")
        return

    args = context.args or []
    if not args:
        await update.message.reply_text("Usage: /approve <user_id>")
        return

    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user_id – must be an integer.")
        return

    db = _db(context)
    if db.approve_user(target_id):
        await update.message.reply_text(
            f"✅ User <code>{target_id}</code> has been approved.",
            parse_mode=ParseMode.HTML,
        )
        # Notify the approved user
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="🎉 Your access has been approved! Send me any URL to get started.",
            )
        except Exception as exc:
            logger.warning("Could not notify user %s: %s", target_id, exc)
    else:
        await update.message.reply_text(
            f"⚠️ No user found with ID <code>{target_id}</code>.",
            parse_mode=ParseMode.HTML,
        )


async def cmd_deny(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Deny a user: /deny <user_id>"""
    user = update.effective_user
    if user is None or not _is_admin(user.id):
        await update.message.reply_text("⛔ This command is for admins only.")
        return

    args = context.args or []
    if not args:
        await update.message.reply_text("Usage: /deny <user_id>")
        return

    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user_id – must be an integer.")
        return

    db = _db(context)
    if db.deny_user(target_id):
        await update.message.reply_text(
            f"❌ User <code>{target_id}</code> has been denied.",
            parse_mode=ParseMode.HTML,
        )
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="❌ Your access request has been denied. Contact the admin for help.",
            )
        except Exception as exc:
            logger.warning("Could not notify user %s: %s", target_id, exc)
    else:
        await update.message.reply_text(
            f"⚠️ No user found with ID <code>{target_id}</code>.",
            parse_mode=ParseMode.HTML,
        )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user statistics (admin only)."""
    user = update.effective_user
    if user is None or not _is_admin(user.id):
        await update.message.reply_text("⛔ This command is for admins only.")
        return

    db = _db(context)
    pending, approved, denied = db.count_by_status()
    await update.message.reply_text(
        f"<b>User Statistics</b>\n\n"
        f"⏳ Pending:  {pending}\n"
        f"✅ Approved: {approved}\n"
        f"❌ Denied:   {denied}\n"
        f"📊 Total:    {pending + approved + denied}",
        parse_mode=ParseMode.HTML,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Link fetching (approved users)
# ──────────────────────────────────────────────────────────────────────────────


async def handle_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle plain text messages from approved users.

    If the message contains a URL, fetch and return its metadata.
    """
    user = update.effective_user
    if user is None:
        return

    db = _db(context)

    if not db.is_approved(user.id):
        row = db.get_user(user.id)
        if row is None:
            await update.message.reply_text(
                "Please use /start to register and request access first."
            )
        elif row["status"] == STATUS_DENIED:
            await update.message.reply_text(
                "❌ Your access has been denied. Contact the admin for help."
            )
        else:
            await update.message.reply_text(
                "⏳ Your access request is still pending approval."
            )
        return

    text = (update.message.text or "").strip()
    if not is_valid_url(text):
        await update.message.reply_text(
            "Please send a valid HTTP/HTTPS URL to fetch its information."
        )
        return

    await update.message.reply_text("⏳ Fetching link info…")
    try:
        info = fetch_link_info(text)
        reply = info.format_message()
        if info.og_image:
            await update.message.reply_photo(
                photo=info.og_image,
                caption=reply,
                parse_mode=ParseMode.HTML,
            )
        else:
            await update.message.reply_text(reply, parse_mode=ParseMode.HTML)
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", text, exc)
        await update.message.reply_text(
            f"⚠️ Could not fetch the link: {exc}"
        )
