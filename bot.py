#!/usr/bin/env python3
import os, time, uuid, logging, requests, threading, json, random
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pymongo import MongoClient

# ============================================================
#                     CONFIG
# ============================================================
BOT_TOKEN  = os.environ.get("BOT_TOKEN", "")
OWNER_ID   = int(os.environ.get("OWNER_ID", "6779799030"))
APP_URL    = os.environ.get("APP_URL", "https://your-app.onrender.com")
MONGO_URI  = os.environ.get("MONGO_URI", "")
BASE_URL   = f"https://api.telegram.org/bot{BOT_TOKEN}"
BOT_USERNAME = ""

# ============================================================
#                     MONGODB
# ============================================================
db_client = None
db        = None

def init_db():
    global db_client, db
    if not MONGO_URI:
        logging.warning("No MONGO_URI — using in-memory storage")
        return
    try:
        db_client = MongoClient(MONGO_URI)
        db        = db_client["tictactoe"]
        logging.info("MongoDB connected!")
    except Exception as e:
        logging.error(f"MongoDB failed: {e}")

def db_save_user(uid, name):
    if db is None: return
    try:
        db.users.update_one({"_id": uid},
            {"$set": {"name": name, "last_seen": datetime.now().isoformat()},
             "$inc": {"games_played": 0},
             "$setOnInsert": {"joined": datetime.now().isoformat()}},
            upsert=True)
    except Exception as e: logging.error(f"db_save_user: {e}")

def db_save_game(game):
    if db is None: return
    try: db.games.update_one({"_id": game["id"]}, {"$set": game}, upsert=True)
    except Exception as e: logging.error(f"db_save_game: {e}")

def db_inc_games(uid):
    if db is None: return
    try: db.users.update_one({"_id": uid}, {"$inc": {"games_played": 1}})
    except: pass

def db_get_top_players(limit=5):
    if db is None: return []
    try: return list(db.users.find().sort("games_played", -1).limit(limit))
    except: return []

def db_get_all_users():
    if db is None: return []
    try: return list(db.users.find())
    except: return []

def db_get_user(uid):
    if db is None: return None
    try: return db.users.find_one({"_id": uid})
    except: return None

# ============================================================
#                     IN-MEMORY (fallback)
# ============================================================
games    = {}
users    = {}
banned   = set()
maintenance = False
stats    = {"total_games": 0, "total_moves": 0}

WIN_LINES = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]

# ============================================================
#                     TELEGRAM HELPERS
# ============================================================
def api(method, **kwargs):
    try:
        r = requests.post(f"{BASE_URL}/{method}", json=kwargs, timeout=15)
        return r.json()
    except Exception as e: logging.error(f"API {method}: {e}"); return {}

def send(chat_id, text, **kwargs):
    return api("sendMessage", chat_id=chat_id, text=text, parse_mode="HTML", **kwargs)

def answer_inline(qid, results):
    return api("answerInlineQuery", inline_query_id=qid, results=results, cache_time=0)

def answer_cb(cbid, text="", alert=False):
    return api("answerCallbackQuery", callback_query_id=cbid, text=text, show_alert=alert)

# ============================================================
#                     GAME LOGIC
# ============================================================
def check_winner(board):
    for a,b,c in WIN_LINES:
        if board[a] and board[a]==board[b]==board[c]: return board[a]
    if all(board): return "draw"
    return None

def create_game(p1_id, p1_name):
    gid        = str(uuid.uuid4())[:8]
    c_sym      = random.choice(["X","O"])
    o_sym      = "O" if c_sym=="X" else "X"
    game = {
        "id": gid, "board": [None]*9, "current": "X",
        "players": {c_sym: {"id": p1_id, "name": p1_name}, o_sym: None},
        "creator_id": p1_id, "creator_sym": c_sym,
        "status": "waiting", "scores": {"X":0,"O":0},
        "msg_id": None, "chat_id": None,
        "created": datetime.now().isoformat()
    }
    games[gid] = game
    stats["total_games"] += 1
    db_save_game(game)
    db_inc_games(p1_id)
    return gid

def web_url(gid, pid, sym):
    g  = games.get(gid, {})
    px = requests.utils.quote(g.get("players",{}).get("X",{}).get("name","Player X") or "Player X")
    po = requests.utils.quote((g.get("players",{}).get("O") or {}).get("name","Waiting...") or "Waiting...")
    return f"{APP_URL}?game_id={gid}&player_id={pid}&symbol={sym}&name_x={px}&name_o={po}&api={APP_URL}"

def game_text(g):
    px  = g["players"]["X"]["name"] if g["players"].get("X") else "—"
    po  = g["players"]["O"]["name"] if g["players"].get("O") else "Waiting for opponent..."
    res = check_winner(g["board"])
    if g["status"]=="waiting":   st="⏳ Waiting for an opponent to join..."
    elif res=="draw":             st="🤝 It's a draw! Well played by both."
    elif res:                     st=f"🏆 <b>{g['players'][res]['name']}</b> wins the game!"
    else:                         st=f"♟️ It's <b>{g['players'][g['current']]['name']}</b>'s turn."
    return (f"🎮 <b>Tic Tac Toe</b>\n\n"
            f"❌ <b>X:</b> {px}  —  Score: {g['scores']['X']}\n"
            f"⭕ <b>O:</b> {po}  —  Score: {g['scores']['O']}\n\n{st}")

# ============================================================
#                     USER COMMANDS
# ============================================================
def cmd_start(msg):
    uid  = msg["from"]["id"]
    name = msg["from"].get("first_name","Player")
    users[uid] = {"name": name, "joined": datetime.now().isoformat()}
    db_save_user(uid, name)
    send(msg["chat"]["id"],
        f"👋 Welcome to <b>Tic Tac Toe</b>!\n\n"
        f"Challenge your friends to a classic game of Tic Tac Toe — right inside Telegram.\n\n"
        f"<b>How to play:</b>\n"
        f"Type <code>@{BOT_USERNAME}</code> in any group or chat, "
        f"then tap the game option to send an invitation.\n"
        f"The first person to click <b>Join</b> becomes your opponent!",
        reply_markup={"inline_keyboard":[[
            {"text":"🎮 Play Now","switch_inline_query":"play"}
        ]]})

# ============================================================
#                     OWNER COMMANDS
# ============================================================
def cmd_stats(msg):
    if msg["from"]["id"]!=OWNER_ID: return
    active   = sum(1 for g in games.values() if g["status"]=="playing")
    waiting  = sum(1 for g in games.values() if g["status"]=="waiting")
    all_users = db_get_all_users() or list(users.values())
    top      = db_get_top_players(5)
    top_txt  = "\n".join(f"  {i+1}. {p.get('name','?')} — {p.get('games_played',0)} games"
                         for i,p in enumerate(top)) or "  No data yet"
    send(msg["chat"]["id"],
        f"📊 <b>Bot Statistics</b>\n\n"
        f"👥 Total Users: <b>{len(all_users)}</b>\n"
        f"🎮 Total Games: <b>{stats['total_games']}</b>\n"
        f"▶️ Active Games: <b>{active}</b>\n"
        f"⏳ Waiting Games: <b>{waiting}</b>\n"
        f"🚫 Banned: <b>{len(banned)}</b>\n"
        f"🔧 Maintenance: <b>{'ON' if maintenance else 'OFF'}</b>\n\n"
        f"🏆 <b>Top Players:</b>\n{top_txt}")

def cmd_activegames(msg):
    if msg["from"]["id"]!=OWNER_ID: return
    active = [g for g in games.values() if g["status"]=="playing"]
    if not active: send(msg["chat"]["id"],"No active games right now."); return
    lines = [f"▶️ <b>Active Games ({len(active)})</b>\n"]
    for g in active[:15]:
        px = g["players"].get("X",{}).get("name","?") if g["players"].get("X") else "?"
        po = g["players"].get("O",{}).get("name","?") if g["players"].get("O") else "?"
        lines.append(f"• <code>{g['id']}</code> — {px} vs {po}")
    send(msg["chat"]["id"],"\n".join(lines))

def cmd_users(msg):
    if msg["from"]["id"]!=OWNER_ID: return
    all_u = db_get_all_users() or list(users.values())
    if not all_u: send(msg["chat"]["id"],"No users yet."); return
    lines = [f"👥 <b>All Users ({len(all_u)})</b>\n"]
    for u in all_u[:20]:
        uid  = u.get("_id") or u.get("id","?")
        name = u.get("name","?")
        gp   = u.get("games_played",0)
        lines.append(f"• <code>{uid}</code> — {name} ({gp} games)")
    if len(all_u)>20: lines.append(f"\n... and {len(all_u)-20} more.")
    send(msg["chat"]["id"],"\n".join(lines))

def cmd_getuser(msg):
    if msg["from"]["id"]!=OWNER_ID: return
    p = msg.get("text","").split()
    if len(p)<2: send(msg["chat"]["id"],"Usage: /getuser &lt;user_id&gt;"); return
    try:
        uid  = int(p[1])
        info = db_get_user(uid) or users.get(uid)
        if info:
            send(msg["chat"]["id"],
                f"👤 <b>User Info</b>\n\n"
                f"ID: <code>{uid}</code>\n"
                f"Name: <b>{info.get('name','?')}</b>\n"
                f"Games: <b>{info.get('games_played',0)}</b>\n"
                f"Joined: {info.get('joined','?')}\n"
                f"Banned: {'Yes' if uid in banned else 'No'}")
        else: send(msg["chat"]["id"],f"User <code>{uid}</code> not found.")
    except: send(msg["chat"]["id"],"Invalid ID.")

def cmd_broadcast(msg):
    if msg["from"]["id"]!=OWNER_ID: return
    text = msg.get("text","").replace("/broadcast","").strip()
    if not text: send(msg["chat"]["id"],"Usage: /broadcast &lt;message&gt;"); return
    all_u = db_get_all_users() or []
    uids  = [u.get("_id") for u in all_u] if all_u else list(users.keys())
    count = 0
    for uid in uids:
        try: send(uid,f"📢 <b>Announcement</b>\n\n{text}"); count+=1; time.sleep(0.05)
        except: pass
    send(msg["chat"]["id"],f"✅ Broadcast sent to <b>{count}</b> users.")

def cmd_ban(msg):
    if msg["from"]["id"]!=OWNER_ID: return
    p=msg.get("text","").split()
    if len(p)<2: send(msg["chat"]["id"],"Usage: /ban &lt;user_id&gt;"); return
    try: uid=int(p[1]); banned.add(uid); send(msg["chat"]["id"],f"🚫 User <code>{uid}</code> banned.")
    except: send(msg["chat"]["id"],"Invalid ID.")

def cmd_unban(msg):
    if msg["from"]["id"]!=OWNER_ID: return
    p=msg.get("text","").split()
    if len(p)<2: send(msg["chat"]["id"],"Usage: /unban &lt;user_id&gt;"); return
    try: uid=int(p[1]); banned.discard(uid); send(msg["chat"]["id"],f"✅ User <code>{uid}</code> unbanned.")
    except: send(msg["chat"]["id"],"Invalid ID.")

def cmd_maintenance(msg):
    global maintenance
    if msg["from"]["id"]!=OWNER_ID: return
    maintenance=not maintenance
    send(msg["chat"]["id"],f"🔧 Maintenance: <b>{'ON' if maintenance else 'OFF'}</b>")

# ============================================================
#                     INLINE QUERY
# ============================================================
def handle_inline(query):
    uid  = query["from"]["id"]
    name = query["from"].get("first_name","Player")
    if uid in banned or (maintenance and uid!=OWNER_ID): return
    gid  = create_game(uid, name)
    users[uid] = {"name":name,"joined":datetime.now().isoformat()}
    db_save_user(uid, name)
    # Pre-generate URL for creator (X or O randomly assigned)
    c_sym = games[gid]["creator_sym"]
    creator_url = web_url(gid, uid, c_sym)
    results=[{
        "type":"article","id":gid,
        "title":"Tic Tac Toe",
        "description":"Challenge a friend to a game!",
        "thumb_url":"https://telegra.ph/file/6165913f4f0bcdce9f5e0.jpg",
        "thumb_width":512,"thumb_height":512,
        "input_message_content":{
            "message_text":
                f"🎮 <b>{name}</b> has challenged you to a game of Tic Tac Toe!\n\n"
                f"Click <b>Join Game</b> to play.",
            "parse_mode":"HTML"},
        "reply_markup":{"inline_keyboard":[[
            {"text":"🎮 Join Game","callback_data":f"join:{gid}:{uid}"},
            {"text":"▶️ Play","callback_data":f"play:{gid}:{uid}"}
        ]]}}]
    answer_inline(query["id"], results)

# ============================================================
#                     CALLBACK QUERY
# ============================================================
def handle_callback(cb):
    uid     = cb["from"]["id"]
    name    = cb["from"].get("first_name","Player")
    data    = cb.get("data","")
    msg     = cb.get("message",{})
    chat_id = msg.get("chat",{}).get("id")
    msg_id  = msg.get("message_id")

    # Handle play button — creator opens their own game
    if data.startswith("play:"):
        parts = data.split(":")
        gid   = parts[1]
        game  = games.get(gid)
        if not game: answer_cb(cb["id"],"Game not found.",True); return
        game_url = f"{APP_URL}/game/{gid}?pid={uid}"
        api("answerCallbackQuery", callback_query_id=cb["id"], url=game_url)
        return

    if not data.startswith("join:"): return
    _,gid,creator_id = data.split(":")
    game = games.get(gid)

    if not game:          answer_cb(cb["id"],"Game not found.",True); return
    if uid in banned:     answer_cb(cb["id"],"You are banned.",True); return

    # Creator can open their own game
    if str(uid)==str(creator_id):
        c_sym    = game.get("creator_sym","X")
        game_url = f"{APP_URL}/game/{gid}?pid={uid}"
        api("answerCallbackQuery", callback_query_id=cb["id"], url=game_url)
        return

    if game["status"]!="waiting": answer_cb(cb["id"],"This game is already in progress.",True); return

    # Assign joiner the remaining symbol
    joiner_sym  = "O" if game["players"].get("X") else "X"
    game["players"][joiner_sym] = {"id":uid,"name":name}
    game["status"]  = "playing"
    game["chat_id"] = chat_id
    game["msg_id"]  = msg_id
    users[uid] = {"name":name,"joined":datetime.now().isoformat()}
    db_save_user(uid, name)
    db_save_game(game)

    creator_sym     = game.get("creator_sym","X")
    creator_id_int  = game.get("creator_id", int(creator_id))
    url_creator     = web_url(gid, creator_id_int, creator_sym)
    url_joiner      = web_url(gid, uid, joiner_sym)

    # Game URLs via /game/ endpoint
    game_url_creator = f"{APP_URL}/game/{gid}?pid={creator_id_int}"
    game_url_joiner  = f"{APP_URL}/game/{gid}?pid={uid}"

    # Update group message
    api("editMessageText",
        chat_id=chat_id, message_id=msg_id,
        text=game_text(game), parse_mode="HTML",
        reply_markup={"inline_keyboard":[[
            {"text":"🎮 Open Game","callback_data":f"play:{gid}"}
        ]]})

    # Open game directly for joiner!
    api("answerCallbackQuery",
        callback_query_id=cb["id"],
        url=game_url_joiner)

# ============================================================
#                     MESSAGE HANDLER
# ============================================================
def handle_message(msg):
    uid  = msg["from"]["id"]
    text = msg.get("text","")
    if uid in banned: return
    if maintenance and uid!=OWNER_ID:
        send(msg["chat"]["id"],"🔧 The bot is currently under maintenance. Please try again later.")
        return
    if   text=="/start":              cmd_start(msg)
    elif text=="/stats":              cmd_stats(msg)
    elif text=="/activegames":        cmd_activegames(msg)
    elif text=="/users":              cmd_users(msg)
    elif text.startswith("/getuser"): cmd_getuser(msg)
    elif text.startswith("/broadcast"): cmd_broadcast(msg)
    elif text.startswith("/ban"):     cmd_ban(msg)
    elif text.startswith("/unban"):   cmd_unban(msg)
    elif text=="/maintenance":        cmd_maintenance(msg)

# ============================================================
#                     REST API SERVER
# ============================================================
class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        if parsed.path in ["/","index.html","/index.html"]:
            try:
                with open("index.html","rb") as f: content=f.read()
                self.send_response(200)
                self.send_header("Content-Type","text/html")
                self.send_header("Access-Control-Allow-Origin","*")
                self.end_headers(); self.wfile.write(content)
            except: self.send_response(404); self.end_headers()
        elif parsed.path=="/state":
            gid  = params.get("game_id",[None])[0]
            game = games.get(gid)
            if game:
                players_out = {}
                for sym,p in game["players"].items():
                    players_out[sym] = {"id": p["id"], "name": p["name"]} if p else None
                self.json_res({"board":game["board"],"current":game["current"],
                    "status":game["status"],"players":players_out})
            else: self.json_res({"error":"not found"},404)
        elif parsed.path=="/health":
            self.json_res({"ok":True})
        elif parsed.path.startswith("/game/"):
            gid  = parsed.path.split("/game/")[1]
            game = games.get(gid)
            if not game: self.send_response(404); self.end_headers(); return
            # Serve index.html with game params embedded
            try:
                with open("index.html","rb") as f: html=f.read().decode()
                # Get player info from Telegram initData (passed as query param)
                pid = params.get("pid",[None])[0]
                sym = None
                if pid:
                    for s,p in game["players"].items():
                        if p and str(p["id"])==str(pid): sym=s; break
                if not sym:
                    # Default — serve waiting page
                    sym = game.get("creator_sym","X")
                    pid = str(game.get("creator_id",""))
                nx = requests.utils.quote(game["players"].get("X",{}).get("name","Player X") or "Player X")
                no = requests.utils.quote((game["players"].get("O") or {}).get("name","Waiting...") or "Waiting...")
                # Inject params into HTML
                inject = f"""<script>
window._GAME_ID="{gid}";
window._PLAYER_ID="{pid}";
window._SYMBOL="{sym}";
window._NAME_X=decodeURIComponent("{nx}");
window._NAME_O=decodeURIComponent("{no}");
window._API_URL="{APP_URL}";
</script>"""
                html = html.replace("</head>", inject+"</head>", 1)
                self.send_response(200)
                self.send_header("Content-Type","text/html")
                self.send_header("Access-Control-Allow-Origin","*")
                self.end_headers()
                self.wfile.write(html.encode())
            except Exception as e:
                logging.error(f"Game serve error: {e}")
                self.send_response(500); self.end_headers()
        else: self.send_response(404); self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length",0))
        body   = self.rfile.read(length)
        parsed = urlparse(self.path)
        try: data=json.loads(body)
        except: data={}

        if parsed.path=="/webhook":
            try:
                if "message"       in data: handle_message(data["message"])
                elif "inline_query" in data: handle_inline(data["inline_query"])
                elif "callback_query" in data: handle_callback(data["callback_query"])
            except Exception as e: logging.error(f"Webhook: {e}")
            self.json_res({"ok":True})

        elif parsed.path=="/move":
            gid=data.get("game_id"); pid=data.get("player_id"); cell=data.get("cell")
            game=games.get(gid)
            if not game or game["status"]!="playing": self.json_res({"error":"invalid"},400); return
            curr=game["players"][game["current"]]
            if str(curr["id"])!=str(pid): self.json_res({"error":"not your turn"},403); return
            if game["board"][cell] is not None: self.json_res({"error":"taken"},400); return
            game["board"][cell]=game["current"]; stats["total_moves"]+=1
            res=check_winner(game["board"])
            if res:
                game["status"]="finished"
                db_save_game(game)
                if game["chat_id"] and game["msg_id"]:
                    api("editMessageText",chat_id=game["chat_id"],message_id=game["msg_id"],
                        text=game_text(game),parse_mode="HTML")
            else:
                game["current"]="O" if game["current"]=="X" else "X"
                db_save_game(game)
            self.json_res({"ok":True,"board":game["board"],"current":game["current"]})

        elif parsed.path=="/result":
            gid=data.get("game_id"); scores=data.get("scores",{})
            game=games.get(gid)
            if game and scores:
                game["scores"]=scores
                db_save_game(game)
            self.json_res({"ok":True})
        else: self.send_response(404); self.end_headers()

    def json_res(self, data, status=200):
        body=json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Access-Control-Allow-Origin","*")
        self.end_headers(); self.wfile.write(body)

    def log_message(self,*a): pass

# ============================================================
#                     POLLING
# ============================================================
def set_webhook():
    global BOT_USERNAME
    # Get bot info
    me = api("getMe")
    if me.get("ok"):
        BOT_USERNAME = me["result"].get("username","TicTacToeBot")
        logging.info(f"Bot: @{BOT_USERNAME}")
    # Set webhook
    webhook_url = f"{APP_URL}/webhook"
    r = api("setWebhook", url=webhook_url, allowed_updates=["message","inline_query","callback_query"])
    if r.get("ok"):
        logging.info(f"Webhook set: {webhook_url}")
    else:
        logging.error(f"Webhook failed: {r}")

# ============================================================
#                     MAIN
# ============================================================
if __name__=="__main__":
    logging.basicConfig(level=logging.INFO,
        format="%(asctime)s — %(levelname)s — %(message)s",
        handlers=[logging.StreamHandler()])
    logging.info("🎮 Tic Tac Toe Bot Starting...")
    init_db()
    port=int(os.environ.get("PORT",8080))
    server=HTTPServer(("0.0.0.0",port),Handler)
    logging.info(f"Server on port {port}")
    set_webhook()
    server.serve_forever()
