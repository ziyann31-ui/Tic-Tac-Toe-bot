#!/usr/bin/env python3
import os, time, uuid, logging, requests, threading, json
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

BOT_TOKEN  = os.environ.get("BOT_TOKEN", "")
OWNER_ID   = int(os.environ.get("OWNER_ID", "6779799030"))
APP_URL    = os.environ.get("APP_URL", "https://your-app.onrender.com")
BASE_URL   = f"https://api.telegram.org/bot{BOT_TOKEN}"

games = {}; users = {}; banned = set()
stats = {"total_games": 0, "total_moves": 0}
maintenance = False
BOT_USERNAME = ""

WIN_LINES = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]

def api(method, **kwargs):
    try:
        r = requests.post(f"{BASE_URL}/{method}", json=kwargs, timeout=15)
        return r.json()
    except Exception as e:
        logging.error(f"API {method}: {e}"); return {}

def send(chat_id, text, **kwargs):
    return api("sendMessage", chat_id=chat_id, text=text, parse_mode="HTML", **kwargs)

def answer_inline(qid, results):
    return api("answerInlineQuery", inline_query_id=qid, results=results, cache_time=0)

def answer_cb(cbid, text="", alert=False):
    return api("answerCallbackQuery", callback_query_id=cbid, text=text, show_alert=alert)

def check_winner(board):
    for a,b,c in WIN_LINES:
        if board[a] and board[a]==board[b]==board[c]: return board[a]
    if all(board): return "draw"
    return None

def create_game(p1_id, p1_name):
    gid = str(uuid.uuid4())[:8]
    games[gid] = {"id":gid,"board":[None]*9,"current":"X",
        "players":{"X":{"id":p1_id,"name":p1_name},"O":None},
        "status":"waiting","scores":{"X":0,"O":0},
        "msg_id":None,"chat_id":None,"created":datetime.now().isoformat()}
    stats["total_games"] += 1
    return gid

def web_url(gid, pid, sym):
    g = games.get(gid, {})
    nx = requests.utils.quote(g.get("players",{}).get("X",{}).get("name","Player X") if g else "Player X")
    no = requests.utils.quote(g.get("players",{}).get("O",{}).get("name","Waiting...") if g and g.get("players",{}).get("O") else "Waiting...")
    return f"{APP_URL}?game_id={gid}&player_id={pid}&symbol={sym}&name_x={nx}&name_o={no}&api={APP_URL}"

def game_text(g):
    px = g["players"]["X"]["name"] if g["players"]["X"] else "—"
    po = g["players"]["O"]["name"] if g["players"]["O"] else "Waiting for opponent..."
    res = check_winner(g["board"])
    if g["status"]=="waiting": st="⏳ Waiting for an opponent to join..."
    elif res=="draw": st="🤝 It's a draw! Well played by both."
    elif res: st=f"🏆 <b>{g['players'][res]['name']}</b> wins the game!"
    else: st=f"♟️ It's <b>{g['players'][g['current']]['name']}</b>'s turn."
    return (f"🎮 <b>Tic Tac Toe</b>\n\n"
            f"❌ <b>X:</b> {px}  —  Score: {g['scores']['X']}\n"
            f"⭕ <b>O:</b> {po}  —  Score: {g['scores']['O']}\n\n{st}")

def cmd_start(msg):
    uid = msg["from"]["id"]; name = msg["from"].get("first_name","Player")
    users[uid] = {"name":name,"joined":datetime.now().isoformat()}
    send(msg["chat"]["id"],
        f"👋 Welcome to <b>Tic Tac Toe</b>!\n\n"
        f"Challenge your friends to a classic game of Tic Tac Toe — right inside Telegram.\n\n"
        f"<b>How to play:</b>\nType <code>@{BOT_USERNAME}</code> in any group or chat, "
        f"then tap the game option to send an invitation.\n"
        f"The first person to click <b>Join</b> becomes your opponent!",
        reply_markup={"inline_keyboard":[[{"text":"🎮 Play Now","switch_inline_query":"play"}]]})

def cmd_stats(msg):
    if msg["from"]["id"]!=OWNER_ID: return
    active = sum(1 for g in games.values() if g["status"]=="playing")
    send(msg["chat"]["id"],
        f"📊 <b>Bot Statistics</b>\n\n"
        f"👥 Total Users: <b>{len(users)}</b>\n"
        f"🎮 Total Games: <b>{stats['total_games']}</b>\n"
        f"▶️ Active Games: <b>{active}</b>\n"
        f"🚫 Banned Users: <b>{len(banned)}</b>\n"
        f"🔧 Maintenance: <b>{'ON' if maintenance else 'OFF'}</b>")

def cmd_broadcast(msg):
    if msg["from"]["id"]!=OWNER_ID: return
    text = msg.get("text","").replace("/broadcast","").strip()
    if not text: send(msg["chat"]["id"],"Usage: /broadcast &lt;message&gt;"); return
    count=0
    for uid in users:
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

def cmd_getuser(msg):
    if msg["from"]["id"]!=OWNER_ID: return
    p=msg.get("text","").split()
    if len(p)<2: send(msg["chat"]["id"],"Usage: /getuser &lt;user_id&gt;"); return
    try:
        uid=int(p[1]); info=users.get(uid)
        if info: send(msg["chat"]["id"],f"👤 <b>User Info</b>\n\nID: <code>{uid}</code>\nName: <b>{info['name']}</b>\nJoined: {info['joined']}\nBanned: {'Yes' if uid in banned else 'No'}")
        else: send(msg["chat"]["id"],f"User <code>{uid}</code> not found.")
    except: send(msg["chat"]["id"],"Invalid ID.")

def cmd_users(msg):
    if msg["from"]["id"]!=OWNER_ID: return
    if not users: send(msg["chat"]["id"],"No users yet."); return
    lines=[f"👥 <b>All Users ({len(users)})</b>\n"]
    for uid,info in list(users.items())[:20]: lines.append(f"• <code>{uid}</code> — {info['name']}")
    if len(users)>20: lines.append(f"\n... and {len(users)-20} more.")
    send(msg["chat"]["id"],"\n".join(lines))

def cmd_maintenance(msg):
    global maintenance
    if msg["from"]["id"]!=OWNER_ID: return
    maintenance=not maintenance
    send(msg["chat"]["id"],f"🔧 Maintenance: <b>{'ON' if maintenance else 'OFF'}</b>")

def handle_inline(query):
    uid=query["from"]["id"]; name=query["from"].get("first_name","Player")
    if uid in banned or (maintenance and uid!=OWNER_ID): return
    gid=create_game(uid,name)
    results=[{"type":"article","id":gid,"title":"🎮 Tic Tac Toe",
        "description":"Challenge someone to a game of Tic Tac Toe!",
        "thumb_url":"https://img.icons8.com/color/96/tic-tac-toe.png",
        "thumb_width":96,"thumb_height":96,
        "input_message_content":{"message_text":
            f"🎮 <b>{name}</b> has challenged you to a game of Tic Tac Toe!\n\n"
            f"Click the button below to accept the challenge and join the game.",
            "parse_mode":"HTML"},
        "reply_markup":{"inline_keyboard":[[{"text":"🎮 Join Game","callback_data":f"join:{gid}:{uid}"}]]}}]
    answer_inline(query["id"],results)

def handle_callback(cb):
    uid=cb["from"]["id"]; name=cb["from"].get("first_name","Player")
    data=cb.get("data",""); msg=cb.get("message",{})
    chat_id=msg.get("chat",{}).get("id"); msg_id=msg.get("message_id")
    if not data.startswith("join:"): return
    _,gid,creator_id=data.split(":")
    game=games.get(gid)
    if not game: answer_cb(cb["id"],"Game not found.",True); return
    if uid in banned: answer_cb(cb["id"],"You are banned.",True); return
    if str(uid)==creator_id: answer_cb(cb["id"],"You cannot join your own game!",True); return
    if game["status"]!="waiting": answer_cb(cb["id"],"This game is already in progress.",True); return
    game["players"]["O"]={"id":uid,"name":name}
    game["status"]="playing"; game["chat_id"]=chat_id; game["msg_id"]=msg_id
    users[uid]={"name":name,"joined":datetime.now().isoformat()}
    url_x=web_url(gid,int(creator_id),"X")
    api("editMessageText",chat_id=chat_id,message_id=msg_id,
        text=game_text(game),parse_mode="HTML",
        reply_markup={"inline_keyboard":[[{"text":"🎮 Open Game","web_app":{"url":url_x}}]]})
    answer_cb(cb["id"])

def handle_message(msg):
    uid=msg["from"]["id"]; text=msg.get("text","")
    if uid in banned: return
    if maintenance and uid!=OWNER_ID:
        send(msg["chat"]["id"],"🔧 The bot is currently under maintenance. Please try again later."); return
    if text=="/start": cmd_start(msg)
    elif text=="/stats": cmd_stats(msg)
    elif text.startswith("/broadcast"): cmd_broadcast(msg)
    elif text.startswith("/ban"): cmd_ban(msg)
    elif text.startswith("/unban"): cmd_unban(msg)
    elif text.startswith("/getuser"): cmd_getuser(msg)
    elif text=="/users": cmd_users(msg)
    elif text=="/maintenance": cmd_maintenance(msg)

class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed=urlparse(self.path); params=parse_qs(parsed.query)
        if parsed.path in ["/","index.html","/index.html"]:
            try:
                with open("index.html","rb") as f: content=f.read()
                self.send_response(200)
                self.send_header("Content-Type","text/html")
                self.send_header("Access-Control-Allow-Origin","*")
                self.end_headers(); self.wfile.write(content)
            except: self.send_response(404); self.end_headers()
        elif parsed.path=="/state":
            gid=params.get("game_id",[None])[0]; game=games.get(gid)
            if game: self.json_res({"board":game["board"],"current":game["current"],"status":game["status"]})
            else: self.json_res({"error":"not found"},404)
        elif parsed.path=="/health":
            self.json_res({"ok":True})
        else: self.send_response(404); self.end_headers()

    def do_POST(self):
        length=int(self.headers.get("Content-Length",0))
        body=self.rfile.read(length); parsed=urlparse(self.path)
        try: data=json.loads(body)
        except: data={}
        if parsed.path=="/webhook":
            try:
                if "message" in data: handle_message(data["message"])
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
                if game["chat_id"] and game["msg_id"]:
                    api("editMessageText",chat_id=game["chat_id"],message_id=game["msg_id"],
                        text=game_text(game),parse_mode="HTML")
            else: game["current"]="O" if game["current"]=="X" else "X"
            self.json_res({"ok":True,"board":game["board"],"current":game["current"]})
        elif parsed.path=="/result":
            gid=data.get("game_id"); scores=data.get("scores",{})
            game=games.get(gid)
            if game and scores: game["scores"]=scores
            self.json_res({"ok":True})
        else: self.send_response(404); self.end_headers()

    def json_res(self, data, status=200):
        body=json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Access-Control-Allow-Origin","*")
        self.end_headers(); self.wfile.write(body)

    def log_message(self,*a): pass

last_uid=0
def poll():
    global last_uid, BOT_USERNAME
    me=api("getMe")
    if me.get("ok"): BOT_USERNAME=me["result"].get("username","TicTacToeBot"); logging.info(f"Bot: @{BOT_USERNAME}")
    while True:
        try:
            r=requests.get(f"{BASE_URL}/getUpdates",params={"offset":last_uid+1,"timeout":30},timeout=40)
            r.raise_for_status()
            for upd in r.json().get("result",[]):
                last_uid=upd["update_id"]
                if "message" in upd: handle_message(upd["message"])
                if "inline_query" in upd: handle_inline(upd["inline_query"])
                if "callback_query" in upd: handle_callback(upd["callback_query"])
        except Exception as e: logging.error(f"Poll: {e}"); time.sleep(5)

if __name__=="__main__":
    logging.basicConfig(level=logging.INFO,format="%(asctime)s — %(levelname)s — %(message)s",handlers=[logging.StreamHandler()])
    logging.info("🎮 Tic Tac Toe Bot Starting...")
    port=int(os.environ.get("PORT",8080))
    server=HTTPServer(("0.0.0.0",port),Handler)
    logging.info(f"Server on port {port}")
    threading.Thread(target=poll,daemon=True).start()
    server.serve_forever()
