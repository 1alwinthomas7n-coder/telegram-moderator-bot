from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import asyncio
import os


# ==============================
# BOT TOKEN
# ==============================

import asyncio


# ==============================
# BOT TOKEN
# ==============================

BOT_TOKEN = os.getenv("BOT_TOKEN")
print("BOT_TOKEN loaded:", bool(BOT_TOKEN), "length:", len(BOT_TOKEN or ""))


# ==============================
# VOTING STORAGE
# ==============================

active_votes = {}


# ==============================
# CHECK @ADMIN / @ADMINS
# ==============================

def contains_admin_mention(message):

    if not message.text or not message.entities:
        return False

    # Mention must be in a reply
    if not message.reply_to_message:
        return False

    for entity in message.entities:

        if entity.type == "mention":

            username = message.text[
                entity.offset:
                entity.offset + entity.length
            ].lower()

            if username in ["@admin", "@admins"]:
                return True

    return False

def get_target_user(message):

    # If B replied to A's message,
    # A is the target.

    if message.reply_to_message:

        if message.reply_to_message.from_user:

            return message.reply_to_message.from_user

    # If there is no reply,
    # the person mentioning admin is target.

    if message.from_user:
        return message.from_user

    return None


# ==============================
# GET USER NAME
# ==============================

def get_full_name(user):

    name = user.first_name or ""

    if user.last_name:
        name += " " + user.last_name

    return name.strip()


# ==============================
# CREATE PROGRESS BAR
# ==============================

def progress_bar(total_votes):

    if total_votes == 0:
        return "⬜⬜⬜⬜⬜⬜"

    if total_votes == 1:
        return "🟦🟦⬜⬜⬜⬜"

    if total_votes == 2:
        return "🟦🟦🟦🟦⬜⬜"

    return "🟦🟦🟦🟦🟦🟦"


# ==============================
# CREATE VOTE TEXT
# ==============================

def create_vote_text(vote):

    yes_count = len(vote["yes_votes"])
    no_count = len(vote["no_votes"])

    total_votes = yes_count + no_count

    yes_percentage = (yes_count / 3) * 100
    no_percentage = (no_count / 3) * 100

    target_name = vote["target_name"]
    reporter_name = vote["reporter_name"]

    bar = progress_bar(total_votes)

    text = (
        "⚠️ ADMIN REPORT\n\n"
        f"👤 Target: {target_name}\n"
        f"🛡 Reported by: {reporter_name}\n\n"
        f"Should **{target_name}** be removed from the group?\n\n"
        f"{bar}\n"
        f"🟢 YES — **{yes_count} votes — {yes_percentage:.1f}%**\n"
        f"🔴 NO — **{no_count} votes — {no_percentage:.1f}%**\n\n"
        f"🗳 Total Votes: **{total_votes}/3**\n\n"
        "You can vote using the buttons below."
    )

    return text


# ==============================
# VOTE BUTTONS
# ==============================

def create_buttons(vote_id):

    keyboard = [

        [
            InlineKeyboardButton(
                "🟢 YES",
                callback_data=f"YES:{vote_id}"
            ),

            InlineKeyboardButton(
                "🔴 NO",
                callback_data=f"NO:{vote_id}"
            )
        ]

    ]

    return InlineKeyboardMarkup(keyboard)


# ==============================
# HANDLE GROUP MESSAGE
# ==============================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    message = update.message

    # Only groups
    if message.chat.type not in [
        "group",
        "supergroup"
    ]:
        return

    # Only text
    if not message.text:
        return

    # Check @admin / @admins
    if not contains_admin_mention(message):
        return

    # Ignore bots
    if message.from_user:

        if message.from_user.is_bot:
            return

    # ==============================
    # FIND TARGET
    # ==============================

    target_user = get_target_user(message)

    if not target_user:
        return

    target_name = get_full_name(
        target_user
    )

    reporter_name = get_full_name(
        message.from_user
    )

    # ==============================
    # UNIQUE VOTE ID
    # ==============================

    vote_id = (
        f"{message.chat.id}_"
        f"{message.message_id}"
    )

    # ==============================
    # SAVE VOTE
    # ==============================

    active_votes[vote_id] = {

        "chat_id": message.chat.id,

        "target_user_id": target_user.id,

        "target_name": target_name,

        "reporter_name": reporter_name,

        "yes_votes": set(),

        "no_votes": set(),

        "vote_message_id": None,

        "finished": False
    }

    vote = active_votes[vote_id]

    # ==============================
    # SEND VOTING MESSAGE
    # ==============================

    vote_message = await context.bot.send_message(

        chat_id=message.chat.id,

        text=create_vote_text(vote),

        parse_mode="Markdown",

        reply_markup=create_buttons(
            vote_id
        ),

        reply_to_message_id=message.message_id
    )

    vote["vote_message_id"] = (
        vote_message.message_id
    )

    print("==============================")
    print("NEW ADMIN REPORT")
    print(f"TARGET: {target_name}")
    print(f"REPORTED BY: {reporter_name}")
    print(f"VOTE ID: {vote_id}")
    print("==============================")


    # ==============================
    # 15 MINUTE TIMER
    # ==============================

    context.application.create_task(
        vote_timeout(
            context.application,
            vote_id
        )
    )


# ==============================
# HANDLE YES / NO BUTTON
# ==============================

async def handle_vote(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    data = query.data

    if not data:
        return

    try:

        choice, vote_id = data.split(
            ":",
            1
        )

    except ValueError:
        return

    # ==============================
    # CHECK VOTE EXISTS
    # ==============================

    if vote_id not in active_votes:

        await query.answer(
            "This vote is no longer active.",
            show_alert=True
        )

        return

    vote = active_votes[vote_id]

    if vote["finished"]:

        await query.answer(
            "This vote has already finished.",
            show_alert=True
        )

        return

    user_id = query.from_user.id

    # ==============================
    # REMOVE OLD VOTE
    # ==============================

    vote["yes_votes"].discard(
        user_id
    )

    vote["no_votes"].discard(
        user_id
    )

    # ==============================
    # SAVE NEW VOTE
    # ==============================

    if choice == "YES":

        vote["yes_votes"].add(
            user_id
        )

    elif choice == "NO":

        vote["no_votes"].add(
            user_id
        )

    yes_count = len(
        vote["yes_votes"]
    )

    no_count = len(
        vote["no_votes"]
    )

    total_votes = (
        yes_count + no_count
    )

    print(
        f"Vote {vote_id}: "
        f"YES={yes_count} "
        f"NO={no_count}"
    )

    # ==============================
    # 3 YES → BAN
    # ==============================

    if yes_count >= 3:

        vote["finished"] = True

        try:

            await context.bot.ban_chat_member(

                chat_id=vote["chat_id"],

                user_id=vote["target_user_id"]
            )

            print(
                f"SUCCESS: "
                f"{vote['target_name']} "
                f"was banned."
            )

        except Exception as e:

            print(
                "BAN ERROR:",
                e
            )

        # Delete voting message

        try:

            await context.bot.delete_message(

                chat_id=vote["chat_id"],

                message_id=vote["vote_message_id"]
            )

        except Exception as e:

            print(
                "DELETE ERROR:",
                e
            )

        await context.bot.send_message(

            chat_id=vote["chat_id"],

            text=(
                "🚫 ALL BAN\n\n"
                f"👤 {vote['target_name']} has been banned by the group vote."
            )
        )

        return

    # ==============================
    # 3 NO → KEEP
    # ==============================

    if no_count >= 3:

        vote["finished"] = True

        print(
            f"KEEP: "
            f"{vote['target_name']} "
            f"will not be removed."
        )

        try:

            await context.bot.delete_message(

                chat_id=vote["chat_id"],

                message_id=vote["vote_message_id"]
            )

        except Exception as e:

            print(
                "DELETE ERROR:",
                e
            )

        return

    # ==============================
    # UPDATE MESSAGE
    # ==============================

    try:

        await query.edit_message_text(

            text=create_vote_text(vote),

            parse_mode="Markdown",

            reply_markup=create_buttons(
                vote_id
            )
        )

    except Exception as e:

        print(
            "UPDATE VOTE ERROR:",
            e
        )


# ==============================
# 15 MINUTE TIMEOUT
# ==============================

async def vote_timeout(
    application,
    vote_id
):

    await asyncio.sleep(
        15 * 60
    )

    if vote_id not in active_votes:
        return

    vote = active_votes[vote_id]

    if vote["finished"]:
        return

    vote["finished"] = True

    print(
        f"Vote {vote_id} "
        f"expired after 15 minutes."
    )

    try:

        await application.bot.delete_message(

            chat_id=vote["chat_id"],

            message_id=vote["vote_message_id"]
        )

        print(
            "Voting message automatically deleted."
        )

    except Exception as e:

        print(
            "TIMEOUT DELETE ERROR:",
            e
        )


# ==============================
# ERROR HANDLER
# ==============================

async def error_handler(
    update,
    context
):

    print(
        "ERROR:",
        context.error
    )


# ==============================
# MAIN
# ==============================

def main():

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Group messages

    app.add_handler(

        MessageHandler(

            filters.TEXT
            & ~filters.COMMAND,

            handle_message
        )
    )

    # YES / NO buttons

    app.add_handler(

        CallbackQueryHandler(
            handle_vote
        )
    )

    # Error handler

    app.add_error_handler(
        error_handler
    )

    print()
    print("==============================")
    print("🤖 MODERATION BOT IS RUNNING")
    print("==============================")
    print("@admin / @admins → REPORT")
    print("YES / NO → VOTE")
    print("1 vote → 33.3%")
    print("2 votes → 66.7%")
    print("3 votes → 100%")
    print("3 YES → BAN")
    print("3 NO → KEEP")
    print("15 minutes → DELETE")
    print("==============================")
    print()

    app.run_polling()


# ==============================

# FadeHost auto-deploy
# START
# ==============================

if __name__ == "__main__":
    main()
