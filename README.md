# 🎮 XO Verse Bot

<div align="center">

![Tic Tac Toe](https://img.shields.io/badge/Game-Tic%20Tac%20Toe-purple?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python)
![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?style=for-the-badge&logo=telegram)
![MongoDB](https://img.shields.io/badge/MongoDB-Database-green?style=for-the-badge&logo=mongodb)
![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)

**A real-time Tic Tac Toe game bot for Telegram groups — powered by Mini Apps.**

[Play Now](https://t.me/XO_VerseBot) · [Report Bug](https://github.com/ziyann31-ui/Tic-Tac-Toe-bot/issues) · [Request Feature](https://github.com/ziyann31-ui/Tic-Tac-Toe-bot/issues)

</div>

---

## Features

- Real-time gameplay — Play Tic Tac Toe directly inside Telegram
- Instant matchmaking — Send a game invite in any group or chat
- Weekly leaderboard — Top 5 players tracked every week
- Auto leaderboard reset — Every Sunday midnight
- Multiplayer — Challenge any Telegram user
- Random symbol assignment — X or O assigned randomly
- Auto-expire — Game closes if no one joins in 5 minutes
- Admin controls — Full owner command panel

---

## How to Play

1. Open any Telegram group or chat
2. Type `@XO_VerseBot` in the message box
3. Tap the **Tic Tac Toe** option
4. Send the game invite
5. First person to tap **Join Game** becomes your opponent
6. Game opens instantly — no links, no redirects!

---

## Deploy Your Own

### Prerequisites

- Python 3.11+
- MongoDB Atlas account (free tier available)
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)

---

### Option 1 — Railway (Recommended)

Railway is the best option for this bot — no sleep, stable, free tier available.

1. Create account at [railway.app](https://railway.app)
2. New Project → Deploy from GitHub
3. Select your repo
4. Add environment variables (see below)
5. Generate a domain from Settings → Networking
6. Set `APP_URL` to your Railway domain

---

### Option 2 — Render

1. Create account at [render.com](https://render.com)
2. New Web Service → Connect GitHub repo
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `python bot.py`
5. Add environment variables
6. Go to Settings → Overlapping Deploy Policy → set to **Override**

---

### Option 3 — VPS (DigitalOcean / Hostinger / Any Linux)

```bash
# Install Python
sudo apt update && sudo apt install python3 python3-pip -y

# Clone repo
git clone https://github.com/ziyann31-ui/Tic-Tac-Toe-bot.git
cd Tic-Tac-Toe-bot

# Install dependencies
pip3 install -r requirements.txt

# Set environment variables
export BOT_TOKEN=your_token
export OWNER_ID=your_id
export APP_URL=https://yourdomain.com
export MONGO_URI=your_mongo_uri

# Run
python3 bot.py

# Or run with screen (keeps running after logout)
screen -S tictactoe
python3 bot.py
# Ctrl+A then D to detach
```

---

### Environment Variables

```env
BOT_TOKEN=your_telegram_bot_token
OWNER_ID=your_telegram_user_id
APP_URL=https://your-deployment-url
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/tictactoe
```

---

### BotFather Setup

```
/setinline → Enable inline mode for your bot
/newapp    → Create Mini App
  Short name: XOverse
  URL: https://your-deployment-url
```

---

## Bot Commands

### For Everyone

| Command | Description |
|---|---|
| `/start` | Start the bot and see how to play |
| `/leaderboard` | View weekly top 5 players |

### Owner Only

| Command | Description |
|---|---|
| `/stats` | Total users, games, active games |
| `/activegames` | List all active games |
| `/users` | All registered users |
| `/getuser <id>` | Detailed user info |
| `/broadcast <msg>` | Send message to all users |
| `/ban <id>` | Ban a user |
| `/unban <id>` | Unban a user |
| `/maintenance` | Toggle maintenance mode ON/OFF |
| `/resetleaderboard` | Reset weekly wins |

---

## Tech Stack

- **Backend** — Python 3.11
- **Bot Framework** — python-telegram-bot
- **Database** — MongoDB Atlas
- **Frontend** — HTML5 + CSS3 + Vanilla JS
- **Mini App** — Telegram Web App SDK
- **Hosting** — Railway / Render / VPS

---

## Project Structure

```
Tic-Tac-Toe-bot/
├── bot.py           # Main bot + REST API server
├── index.html       # Game UI (Telegram Mini App)
├── requirements.txt # Python dependencies
├── runtime.txt      # Python version
├── Dockerfile       # Docker config
├── Procfile         # Process config
├── render.yaml      # Render config
└── .env.example     # Environment variables template
```

---

## Contributing

Contributions are welcome!

1. Fork the project
2. Create your feature branch: `git checkout -b feature/AmazingFeature`
3. Commit your changes: `git commit -m 'Add AmazingFeature'`
4. Push to the branch: `git push origin feature/AmazingFeature`
5. Open a Pull Request

If you found this project useful, please give it a **star** — it helps others discover it!

---

## License

MIT License

Copyright (c) 2026 ziyann31-ui

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---

Made with love by [@ziyann31-ui](https://github.com/ziyann31-ui) | Bot: [@XO_VerseBot](https://t.me/XO_VerseBot)
