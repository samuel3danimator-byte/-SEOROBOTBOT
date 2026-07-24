import datetime
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

import config
from db import RankHistory, SessionLocal, TrackedKeyword, User, init_db
from scraper import google_rank

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def _get_or_create_user(session, tg_user_id: int, chat_id: int) -> User:
    user = session.query(User).filter_by(telegram_id=tg_user_id).first()
    if not user:
        user = User(telegram_id=tg_user_id, chat_id=chat_id)
        session.add(user)
        session.commit()
    return user


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = SessionLocal()
    _get_or_create_user(session, update.effective_user.id, update.effective_chat.id)
    session.close()
    await update.message.reply_text(
        "Welcome to SEO Robot Bot!\n\n"
        "Commands:\n"
        "/track <keyword> | <domain> — start tracking a keyword\n"
        "/list — show your tracked keywords\n"
        "/remove <id> — stop tracking one\n"
        "/check <id> — check a keyword's rank right now\n"
        "/report — check and report all your keywords now\n\n"
        "You'll also get an automatic daily report."
    )


async def track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)
    if "|" not in text:
        await update.message.reply_text(
            "Usage: /track <keyword> | <domain>\n"
            "Example: /track best coffee maker | mysite.com"
        )
        return

    keyword, domain = [p.strip() for p in text.split("|", 1)]
    if not keyword or not domain:
        await update.message.reply_text("Both a keyword and a domain are required.")
        return

    session = SessionLocal()
    user = _get_or_create_user(session, update.effective_user.id, update.effective_chat.id)
    tk = TrackedKeyword(user_id=user.id, keyword=keyword, domain=domain)
    session.add(tk)
    session.commit()
    tk_id = tk.id
    session.close()

    await update.message.reply_text(
        f'Tracking #{tk_id}: "{keyword}" for {domain}.\n'
        f"It'll be included in your daily report, or run /check {tk_id} now."
    )


async def list_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=update.effective_user.id).first()
    if not user or not user.keywords:
        await update.message.reply_text(
            "You're not tracking anything yet. Use /track <keyword> | <domain>."
        )
        session.close()
        return

    lines = []
    for tk in user.keywords:
        last = (
            session.query(RankHistory)
            .filter_by(keyword_id=tk.id)
            .order_by(RankHistory.checked_at.desc())
            .first()
        )
        pos = last.position if last and last.position else "not found" if last else "not checked yet"
        lines.append(f'#{tk.id} "{tk.keyword}" ({tk.domain}) — position: {pos}')
    session.close()
    await update.message.reply_text("\n".join(lines))


async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /remove <id>")
        return

    tk_id = context.args[0]
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=update.effective_user.id).first()
    tk = None
    if user:
        tk = session.query(TrackedKeyword).filter_by(id=tk_id, user_id=user.id).first()

    if not tk:
        await update.message.reply_text("Not found.")
        session.close()
        return

    session.delete(tk)
    session.commit()
    session.close()
    await update.message.reply_text(f"Removed #{tk_id}.")


async def check_one(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /check <id>")
        return

    tk_id = context.args[0]
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=update.effective_user.id).first()
    tk = None
    if user:
        tk = session.query(TrackedKeyword).filter_by(id=tk_id, user_id=user.id).first()

    if not tk:
        await update.message.reply_text("Not found.")
        session.close()
        return

    keyword, domain = tk.keyword, tk.domain
    tk_id_val = tk.id
    session.close()

    await update.message.reply_text(f'Checking "{keyword}" for {domain}... this can take a bit.')
    pos = google_rank(keyword, domain, max_results=config.MAX_RESULTS, delay=config.SCRAPE_DELAY_SECONDS)

    session = SessionLocal()
    session.add(RankHistory(keyword_id=tk_id_val, position=pos))
    session.commit()
    session.close()

    result = pos if pos else f"not found in top {config.MAX_RESULTS}"
    await update.message.reply_text(f"Position: {result}")


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=update.effective_user.id).first()
    if not user or not user.keywords:
        await update.message.reply_text("Nothing tracked yet.")
        session.close()
        return

    keywords = [(tk.id, tk.keyword, tk.domain) for tk in user.keywords]
    session.close()

    await update.message.reply_text(
        f"Running your report now ({len(keywords)} keyword(s)), this may take a while..."
    )

    lines = []
    session = SessionLocal()
    for tk_id, keyword, domain in keywords:
        pos = google_rank(keyword, domain, max_results=config.MAX_RESULTS, delay=config.SCRAPE_DELAY_SECONDS)
        session.add(RankHistory(keyword_id=tk_id, position=pos))
        result = pos if pos else f"not in top {config.MAX_RESULTS}"
        lines.append(f'"{keyword}" ({domain}): {result}')
    session.commit()
    session.close()

    await update.message.reply_text("\n".join(lines))


async def daily_report_job(context: ContextTypes.DEFAULT_TYPE):
    session = SessionLocal()
    users = session.query(User).all()
    user_data = [(u.chat_id, [(tk.id, tk.keyword, tk.domain) for tk in u.keywords]) for u in users]
    session.close()

    for chat_id, keywords in user_data:
        if not keywords:
            continue

        lines = ["📊 Daily SEO report:"]
        session = SessionLocal()
        for tk_id, keyword, domain in keywords:
            pos = google_rank(
                keyword, domain, max_results=config.MAX_RESULTS, delay=config.SCRAPE_DELAY_SECONDS
            )
            session.add(RankHistory(keyword_id=tk_id, position=pos))
            result = pos if pos else f"not in top {config.MAX_RESULTS}"
            lines.append(f'"{keyword}" ({domain}): {result}')
        session.commit()
        session.close()

        try:
            await context.bot.send_message(chat_id=chat_id, text="\n".join(lines))
        except Exception as e:
            logger.warning(f"Failed to message chat {chat_id}: {e}")


def main():
    init_db()
    app = Application.builder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("track", track))
    app.add_handler(CommandHandler("list", list_keywords))
    app.add_handler(CommandHandler("remove", remove))
    app.add_handler(CommandHandler("check", check_one))
    app.add_handler(CommandHandler("report", report))

    app.job_queue.run_daily(
        daily_report_job,
        time=datetime.time(hour=config.REPORT_HOUR, tzinfo=datetime.timezone.utc),
    )

    logger.info("Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
