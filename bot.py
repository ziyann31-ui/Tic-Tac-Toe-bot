import os
import json
import asyncio
import logging
import random
import string
from datetime import datetime
from threading import Thread

from flask import Flask, send_from_directory
from pymongo import MongoClient
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    InlineQueryResultArticle, InputTextMessageContent, WebAppInfo
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    InlineQueryHandler, ChosenInlineResultHandler,
    ContextTypes, MessageHandler, filters
)
from telegram.constants import ParseMode

# ─── Flask App for Render Web Service ────────
flask_app = Flask(__name__, static_folder='.')

@flask_app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@flask_app.route('/<path:path>')
def serve_file(path):
    return send_from_directory('.', path)

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

# ─── Logging ─────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── Config ──────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
APP_URL = os.getenv("APP_URL", "").rstrip("/")
MONGODB_URI = os.getenv("MONGODB_URI", "")

# ─── MongoDB Setup ───────────────────────────
client = MongoClient(MONGODB_URI)
db = client["tictactoe_bot"]
games_col = db["games"]
users_col = db["users"]
banned_col = db["banned"]
stats_col = db["stats"]

def init_db():
    defaults = [
        {"_id": "total_games", "value": 0},
        {"_id": "total_users", "value": 0},
        {"_id": "active_games", "value": 0},
        {"_id": "total_starts", "value": 0}
    ]
    for stat in defaults:
        stats_col.update_one({"_id": stat["_id"]}, {"$setOnInsert": stat}, upsert=True)

    games_col.create_index("game_id", unique=True)
    users_col.create_index("user_id", unique=True)
    banned_col.create_index("user_id", unique=True)
    logger.info("MongoDB initialized.")

# ─── Helpers ─────────────────────────────────
def generate_game_id():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

def is_banned(user_id: int) -> bool:
    return banned_col.find_one({"user_id": user_id}) is not None

def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

def ensure_user(user_id, username, first_name):
    users_col.update_one(
        {"user_id": user_id},
        {"$setOnInsert": {
            "user_id": user_id,
            "username": username or "",
            "first_name": first_name or "",
            "games_played": 0,
            "games_won": 0,
            "games_drawn": 0,
            "games_lost": 0,
            "total_moves": 0,
            "joined_at": datetime.now().isoformat()
        },
        "$set": {"last_active": datetime.now().isoformat()}},
        upsert=True
    )

def update_user_stats(user_id, result, moves=0):
    if result == "win":
        users_col.update_one(
            {"user_id": user_id},
            {"$inc": {"games_played": 1, "games_won": 1, "total_moves": moves}}
        )
    elif result == "loss":
        users_col.update_one(
            {"user_id": user_id},
            {"$inc": {"games_played": 1, "games_lost": 1, "total_moves": moves}}
        )
    elif result == "draw":
        users_col.update_one(
            {"user_id": user_id},
            {"$inc": {"games_played": 1, "games_drawn": 1, "total_moves": moves}}
        )

# ════════════════════════════════════════════
# NORMAL USER COMMANDS (Only /start)
# ════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_banned(user.id):
        await update.message.reply_text("You are banned from using this bot.")
        return

    ensure_user(user.id, user.username, user.first_name)
    stats_col.update_one({"_id": "total_starts"}, {"$inc": {"value": 1}})

    bot_username = (await context.bot.get_me()).username

    text = (
        "Want to play Tic Tac Toe with any contact from Telegram?

"
        "It's very easy to do so, click the button below or go to the chat which you "
        "want to send the invitation to, type in @" + bot_username + ", and add a space. "
        "You can also send the invitation to a group or channel. In that case, the first "
        "person to click the 'Join' button will be your opponent."
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Play", switch_inline_query="")]
    ])

    await update.message.reply_text(
        text,
        reply_markup=keyboard
    )


# ════════════════════════════════════════════
# OWNER / ADMIN ONLY COMMANDS
# ════════════════════════════════════════════

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("Owner only command.")
        return

    total_games = stats_col.find_one({"_id": "total_games"})["value"]
    total_starts = stats_col.find_one({"_id": "total_starts"})["value"]
    total_users = users_col.count_documents({})
    active_games = games_col.count_documents({"status": {"$in": ["waiting", "playing"]}})
    waiting_games = games_col.count_documents({"status": "waiting"})
    finished_games = games_col.count_documents({"status": "finished"})

    top_players = list(users_col.find().sort("games_won", -1).limit(5))

    text = (
        "Bot Statistics

"
        "Users:
"
        "- Total Users: " + str(total_users) + "
"
        "- Total /start used: " + str(total_starts) + "

"
        "Games:
"
        "- Total Games Played: " + str(total_games) + "
"
        "- Currently Active: " + str(active_games) + "
"
        "- Waiting for opponent: " + str(waiting_games) + "
"
        "- Finished: " + str(finished_games) + "

"
        "Top Players:
"
    )

    for i, p in enumerate(top_players, 1):
        name = p.get("first_name") or p.get("username") or "Unknown"
        text += str(i) + ". " + name + " - " + str(p['games_won']) + " wins / " + str(p['games_played']) + " games
"

    await update.message.reply_text(text)


async def activegames_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("Owner only command.")
        return

    active = list(games_col.find(
        {"status": {"$in": ["waiting", "playing"]}}
    ).sort("created_at", -1))

    if not active:
        await update.message.reply_text("No active games right now.")
        return

    lines = ["Active Games: " + str(len(active)) + "
"]
    for g in active:
        p2 = g.get("player2_name") or "Waiting..."
        status_emoji = "WAITING" if g["status"] == "waiting" else "PLAYING"
        lines.append(
            "[" + status_emoji + "] " + g['game_id'] + " - " + g['player1_name'] + " vs " + p2
        )

    await update.message.reply_text("
".join(lines))


async def users_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("Owner only command.")
        return

    count = users_col.count_documents({})
    recent = list(users_col.find().sort("joined_at", -1).limit(15))

    lines = ["Total Users: " + str(count) + "

Recent Users:"]
    for u in recent:
        name = u.get("first_name") or u.get("username") or "Unknown"
        lines.append(
            "- " + str(u['user_id']) + " - " + name + " | Games: " + str(u['games_played']) + " Wins: " + str(u['games_won'])
        )

    await update.message.reply_text("
".join(lines))


async def getuser_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("Owner only command.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /getuser user_id")
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Please provide a valid user ID.")
        return

    user = users_col.find_one({"user_id": user_id})
    if not user:
        await update.message.reply_text("User not found.")
        return

    win_rate = round(user.get("games_won", 0) / max(user.get("games_played", 1), 1) * 100, 1)

    text = (
        "User Info

"
        "ID: " + str(user['user_id']) + "
"
        "Name: " + str(user.get('first_name', 'N/A')) + "
"
        "Username: @" + str(user.get('username') or 'N/A') + "
"
        "Games Played: " + str(user.get('games_played', 0)) + "
"
        "Wins: " + str(user.get('games_won', 0)) + "
"
        "Losses: " + str(user.get('games_lost', 0)) + "
"
        "Draws: " + str(user.get('games_drawn', 0)) + "
"
        "Win Rate: " + str(win_rate) + "%
"
        "Joined: " + str(user.get('joined_at', 'N/A')[:10]) + "
"
        "Last Active: " + str(user.get('last_active', 'N/A')[:16])
    )
    await update.message.reply_text(text)


async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("Owner only command.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /broadcast Your message here")
        return

    message = " ".join(context.args)
    users = list(users_col.find({}, {"user_id": 1}))

    sent = 0
    failed = 0
    for u in users:
        try:
            await context.bot.send_message(u["user_id"], "Broadcast:

" + message)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1

    await update.message.reply_text("Broadcast sent to " + str(sent) + " users. Failed: " + str(failed))


async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("Owner only command.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /ban user_id")
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Please provide a valid user ID.")
        return

    banned_col.update_one(
        {"user_id": user_id},
        {"$set": {"user_id": user_id, "banned_at": datetime.now().isoformat()}},
        upsert=True
    )

    await update.message.reply_text("User " + str(user_id) + " has been banned.")


async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("Owner only command.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /unban user_id")
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Please provide a valid user ID.")
        return

    banned_col.delete_one({"user_id": user_id})

    await update.message.reply_text("User " + str(user_id) + " has been unbanned.")


async def maintenance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("Owner only command.")
        return

    context.bot_data["maintenance"] = not context.bot_data.get("maintenance", False)
    status = "ON" if context.bot_data["maintenance"] else "OFF"
    await update.message.reply_text("Maintenance mode: " + status)


# ════════════════════════════════════════════
# INLINE QUERY & WEB APP HANDLERS
# ════════════════════════════════════════════

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_banned(user.id):
        await update.inline_query.answer([], cache_time=0)
        return

    ensure_user(user.id, user.username, user.first_name)

    game_id = generate_game_id()
    bot_username = (await context.bot.get_me()).username

    webapp_url = APP_URL + "/?game=" + game_id + "&player1=" + str(user.id) + "&name1=" + (user.first_name or user.username or "Player X")

    results = [
        InlineQueryResultArticle(
            id=game_id,
            title="Tic Tac Toe",
            description="Challenge by " + (user.first_name or "You") + " - Click to play!",
            input_message_content=InputTextMessageContent(
                message_text=(
                    (user.first_name or "Someone") + " has challenged you to a game of Tic Tac Toe!

"
                    "Click the Join button below to accept the challenge and become their opponent."
                )
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Join Game", web_app=WebAppInfo(url=webapp_url))]
            ]),
            thumb_url="https://cdn-icons-png.flaticon.com/512/566/566294.png"
        )
    ]

    games_col.insert_one({
        "game_id": game_id,
        "player1_id": user.id,
        "player1_name": user.first_name or user.username or "Player X",
        "player2_id": None,
        "player2_name": None,
        "status": "waiting",
        "board": [["","",""],["","",""],["","",""]],
        "current_turn": "X",
        "winner": None,
        "inline_message_id": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    })

    await update.inline_query.answer(results, cache_time=0)


async def chosen_inline_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chosen_inline_result
    if not result:
        return

    game_id = result.result_id
    inline_msg_id = result.inline_message_id

    games_col.update_one(
        {"game_id": game_id},
        {"$set": {"inline_message_id": inline_msg_id}}
    )

    logger.info("Game " + game_id + " sent with inline_message_id " + str(inline_msg_id))


async def web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.web_app_data:
        return

    data = json.loads(update.message.web_app_data.data)
    game_id = data.get("game_id")
    action = data.get("action")

    if action == "join":
        player2_id = data.get("player2")
        player2_name = data.get("name2", "Player O")

        games_col.update_one(
            {"game_id": game_id},
            {"$set": {
                "player2_id": player2_id,
                "player2_name": player2_name,
                "status": "playing",
                "updated_at": datetime.now().isoformat()
            }}
        )
        return

    if action == "game_over":
        winner = data.get("winner")
        p1_moves = data.get("p1_moves", 0)
        p2_moves = data.get("p2_moves", 0)

        game = games_col.find_one({"game_id": game_id})
        if not game:
            return

        games_col.update_one(
            {"game_id": game_id},
            {"$set": {
                "status": "finished",
                "winner": winner,
                "updated_at": datetime.now().isoformat()
            }}
        )
        stats_col.update_one({"_id": "total_games"}, {"$inc": {"value": 1}})

        p1_id = game["player1_id"]
        p2_id = game.get("player2_id")

        if winner == "draw":
            update_user_stats(p1_id, "draw", p1_moves)
            if p2_id:
                update_user_stats(p2_id, "draw", p2_moves)
        elif winner == "X":
            update_user_stats(p1_id, "win", p1_moves)
            if p2_id:
                update_user_stats(p2_id, "loss", p2_moves)
        else:
            update_user_stats(p1_id, "loss", p1_moves)
            if p2_id:
                update_user_stats(p2_id, "win", p2_moves)

        inline_msg_id = game.get("inline_message_id")

        if inline_msg_id:
            p1_name = game["player1_name"]
            p2_name = game.get("player2_name") or "Player O"

            if winner == "draw":
                text = "It's a draw! Well played by both players."
            elif winner == "X":
                text = p1_name + " wins the game! Better luck next time, " + p2_name + "."
            else:
                text = p2_name + " wins the game! Better luck next time, " + p1_name + "."

            try:
                await context.bot.edit_message_text(
                    text,
                    inline_message_id=inline_msg_id
                )
            except Exception as e:
                logger.warning("Could not update inline message: " + str(e))


# ════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════

async def post_init(app: Application):
    init_db()
    app.bot_data["maintenance"] = False
    logger.info("Bot initialized with MongoDB.")


def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN environment variable is required!")
    if not MONGODB_URI:
        raise ValueError("MONGODB_URI environment variable is required!")

    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    logger.info("Flask server started on background thread.")

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # Normal user commands
    app.add_handler(CommandHandler("start", start))

    # Owner commands
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("activegames", activegames_cmd))
    app.add_handler(CommandHandler("users", users_cmd))
    app.add_handler(CommandHandler("getuser", getuser_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CommandHandler("maintenance", maintenance_cmd))

    # Inline & Web App
    app.add_handler(InlineQueryHandler(inline_query))
    app.add_handler(ChosenInlineResultHandler(chosen_inline_result))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data))

    logger.info("Starting bot polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()