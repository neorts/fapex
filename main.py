"""
Apex Tracker - Ana Program
Web panel + Discord bot tek dosyada birleştirilmiştir.
"""
import os
import threading
import time
from datetime import datetime, timedelta

from flask import Flask, render_template, redirect, url_for

from tracker_core import (
    init_database, get_latest, get_history, get_changes,
    get_player_data, save_player, detect_changes, data_changed,
    format_rank, calculate_rp_change, get_rp_stats,
    get_weekly_trends, get_rank_distribution, get_daily_rp_summary,
    logger, DB_NAME, AUTO_CHECK_INTERVAL, load_env
)
from discord_notifier import (
    notify_rp_change, notify_rank_change, notify_level_change,
    notify_api_error, notify_tracker_started
)

# =========================================================
# FLASK WEB PANEL
# =========================================================

app = Flask(__name__)

tracker_status = {
    "active": True,
    "last_check": None,
    "last_success": None,
    "last_error": None,
    "next_check": None
}


def update_player():
    try:
        tracker_status["last_check"] = datetime.now()

        new_data = get_player_data()
        old_data = get_latest()

        if data_changed(old_data, new_data):
            if old_data is not None:
                changes = detect_changes(old_data, new_data)
                for change in changes:
                    logger.info(f"Değişiklik: {change}")

                # Discord bildirimleri
                if old_data["rank_score"] is not None and new_data["rank_score"] is not None:
                    if old_data["rank_score"] != new_data["rank_score"]:
                        notify_rp_change(
                            old_data["rank_score"],
                            new_data["rank_score"],
                            new_data["name"],
                            format_rank(new_data)
                        )

                old_rank = format_rank(old_data)
                new_rank = format_rank(new_data)
                if old_rank != new_rank:
                    notify_rank_change(old_rank, new_rank, new_data["name"], new_data["rank_score"])

                if old_data["level"] is not None and new_data["level"] is not None:
                    if old_data["level"] != new_data["level"]:
                        notify_level_change(old_data["level"], new_data["level"], new_data["name"])

            save_player(new_data)
            logger.info(f"Kayıt: {new_data['name']} | {format_rank(new_data)} | {new_data['rank_score']} RP")
        else:
            logger.info("Değişiklik yok")

        tracker_status["last_success"] = datetime.now()
        tracker_status["last_error"] = None
        tracker_status["next_check"] = datetime.now() + timedelta(seconds=AUTO_CHECK_INTERVAL)

        return True

    except Exception as e:
        tracker_status["last_error"] = str(e)
        tracker_status["next_check"] = datetime.now() + timedelta(seconds=AUTO_CHECK_INTERVAL)
        logger.error(f"API hatası: {e}")
        notify_api_error(str(e))
        return False


def automatic_tracker():
    logger.info("Otomatik takip başladı")
    update_player()

    while True:
        time.sleep(AUTO_CHECK_INTERVAL)
        update_player()


@app.route("/")
def index():
    player = get_latest()
    history = get_history(30)
    changes = get_changes(20)
    rp_change = calculate_rp_change()

    daily_stats = get_rp_stats(today=True)
    stats_24h = get_rp_stats(hours=24)
    stats_1h = get_rp_stats(hours=1)

    weekly_trends = get_weekly_trends()
    rank_distribution = get_rank_distribution()
    daily_rp_summary = get_daily_rp_summary()

    return render_template(
        "index.html",
        player=player,
        history=history,
        changes=changes,
        rp_change=rp_change,
        daily_stats=daily_stats,
        stats_24h=stats_24h,
        stats_1h=stats_1h,
        weekly_trends=weekly_trends,
        rank_distribution=rank_distribution,
        daily_rp_summary=daily_rp_summary
    )


@app.route("/status")
def status():
    return {
        "active": tracker_status["active"],
        "last_check": tracker_status["last_check"].strftime("%Y-%m-%d %H:%M:%S") if tracker_status["last_check"] else None,
        "last_success": tracker_status["last_success"].strftime("%Y-%m-%d %H:%M:%S") if tracker_status["last_success"] else None,
        "last_error": tracker_status["last_error"],
        "next_check": tracker_status["next_check"].strftime("%Y-%m-%d %H:%M:%S") if tracker_status["next_check"] else None,
        "interval": AUTO_CHECK_INTERVAL
    }


@app.route("/update")
def update():
    update_player()
    return redirect(url_for("index"))


@app.route("/test-discord")
def test_discord():
    from discord_notifier import send_discord_notification
    success = send_discord_notification(
        "🔔 Test Bildirimi",
        "Apex Tracker Discord bağlantısı başarılı! 🎮",
        color=0x43d17a
    )
    if success:
        return {"success": True, "message": "Discord test bildirimi gönderildi!"}
    else:
        return {"success": False, "message": "Webhook URL tanımlı değil veya hata oluştu"}


@app.route("/notifications")
def notification_settings():
    from discord_notifier import (
        DISCORD_WEBHOOK_URL, RP_ALERT_THRESHOLD,
        RANK_CHANGE_ALERT, LEVEL_CHANGE_ALERT, ERROR_ALERT
    )
    return {
        "webhook_configured": bool(DISCORD_WEBHOOK_URL),
        "rp_threshold": RP_ALERT_THRESHOLD,
        "rank_alerts": RANK_CHANGE_ALERT,
        "level_alerts": LEVEL_CHANGE_ALERT,
        "error_alerts": ERROR_ALERT
    }


@app.route("/history")
def history():
    records = get_history(200)
    return render_template("history.html", records=records)


# =========================================================
# DISCORD BOT
# =========================================================

import discord
from discord.ext import commands

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    logger.info(f"Discord Bot hazır: {bot.user.name} ({bot.user.id})")


@bot.command(name="rp")
async def cmd_rp(ctx):
    player = get_latest()
    if not player:
        await ctx.send("❌ Henüz veri yok.")
        return

    embed = discord.Embed(title="🎮 Mevcut RP", color=0xeb4d4d, timestamp=datetime.utcnow())
    embed.add_field(name="Oyuncu", value=player["name"], inline=True)
    embed.add_field(name="Rank", value=format_rank(player), inline=True)
    embed.add_field(name="RP", value=f"**{player['rank_score']}**", inline=True)
    embed.add_field(name="Level", value=str(player["level"]), inline=True)

    rp_change = calculate_rp_change()
    if rp_change > 0:
        embed.add_field(name="Son Değişim", value=f"+{rp_change} RP 🟢", inline=True)
    elif rp_change < 0:
        embed.add_field(name="Son Değişim", value=f"{rp_change} RP 🔴", inline=True)
    else:
        embed.add_field(name="Son Değişim", value="Değişiklik yok ⚪", inline=True)

    await ctx.send(embed=embed)


@bot.command(name="rank")
async def cmd_rank(ctx):
    player = get_latest()
    if not player:
        await ctx.send("❌ Henüz veri yok.")
        return

    embed = discord.Embed(title="🏆 Mevcut Rank", color=0xb98cff, timestamp=datetime.utcnow())
    embed.add_field(name="Oyuncu", value=player["name"], inline=True)
    embed.add_field(name="Rank", value=format_rank(player), inline=True)
    embed.add_field(name="RP", value=f"**{player['rank_score']}**", inline=True)
    embed.add_field(name="Level", value=str(player["level"]), inline=True)

    await ctx.send(embed=embed)


@bot.command(name="stats")
async def cmd_stats(ctx):
    daily = get_rp_stats(today=True)
    stats_24h = get_rp_stats(hours=24)
    stats_1h = get_rp_stats(hours=1)

    embed = discord.Embed(title="📊 İstatistikler", color=0x6ea9ff, timestamp=datetime.utcnow())

    embed.add_field(
        name="📅 Bugün",
        value=f"Net: **{daily['net_change']:+d}** RP\nKazanılan: **+{daily['gained']}** RP\nKaybedilen: **-{daily['lost']}** RP",
        inline=True
    )
    embed.add_field(
        name="⏰ Son 24 Saat",
        value=f"Net: **{stats_24h['net_change']:+d}** RP\nKazanılan: **+{stats_24h['gained']}** RP\nKaybedilen: **-{stats_24h['lost']}** RP",
        inline=True
    )
    embed.add_field(
        name="⏱️ Son 1 Saat",
        value=f"Net: **{stats_1h['net_change']:+d}** RP\nKazanılan: **+{stats_1h['gained']}** RP\nKaybedilen: **-{stats_1h['lost']}** RP",
        inline=True
    )

    await ctx.send(embed=embed)


@bot.command(name="history")
async def cmd_history(ctx):
    changes = get_changes(5)

    if not changes:
        await ctx.send("❌ Henüz değişiklik kaydı yok.")
        return

    embed = discord.Embed(title="📜 Son Değişiklikler", color=0xeb4d4d, timestamp=datetime.utcnow())

    for change in changes:
        change_type = change["change_type"]
        old_val = change["old_value"]
        new_val = change["new_value"]
        diff = change["difference"]
        date = change["recorded_at"]

        if change_type == "RP":
            if diff and diff > 0:
                value = f"{old_val} → {new_val} (**+{diff}** RP) 🟢"
            else:
                value = f"{old_val} → {new_val} (**{diff}** RP) 🔴"
        elif change_type == "RANK":
            value = f"{old_val} → {new_val} 🟣"
        elif change_type == "LEVEL":
            value = f"Level {old_val} → {new_val} 🔵"
        else:
            value = f"{old_val} → {new_val}"

        embed.add_field(name=f"{change_type} — {date}", value=value, inline=False)

    await ctx.send(embed=embed)


@bot.command(name="status")
async def cmd_status(ctx):
    embed = discord.Embed(title="⚙️ Tracker Durumu", color=0x43d17a, timestamp=datetime.utcnow())

    status = "🟢 Aktif" if tracker_status["active"] else "🔴 Pasif"
    embed.add_field(name="Durum", value=status, inline=True)
    embed.add_field(name="Kontrol Aralığı", value=f"{AUTO_CHECK_INTERVAL} saniye", inline=True)

    if tracker_status["last_check"]:
        embed.add_field(name="Son Kontrol", value=tracker_status["last_check"].strftime("%Y-%m-%d %H:%M:%S"), inline=True)
    if tracker_status["last_success"]:
        embed.add_field(name="Son Başarılı", value=tracker_status["last_success"].strftime("%Y-%m-%d %H:%M:%S"), inline=True)
    if tracker_status["next_check"]:
        embed.add_field(name="Sonraki Kontrol", value=tracker_status["next_check"].strftime("%Y-%m-%d %H:%M:%S"), inline=True)
    if tracker_status["last_error"]:
        embed.add_field(name="Son Hata", value=tracker_status["last_error"], inline=False)

    await ctx.send(embed=embed)


@bot.command(name="h4")
async def cmd_h4(ctx):
    stats = get_rp_stats(hours=4)
    net = stats["net_change"]
    emoji = "🟢" if net > 0 else ("🔴" if net < 0 else "⚪")
    sign = "+" if net > 0 else ""

    embed = discord.Embed(title="⏱️ Son 4 Saat RP Değişimi", color=0x6ea9ff, timestamp=datetime.utcnow())
    embed.add_field(name="Net Değişim", value=f"**{sign}{net}** RP {emoji}", inline=True)
    embed.add_field(name="Kazanılan", value=f"+{stats['gained']} RP", inline=True)
    embed.add_field(name="Kaybedilen", value=f"-{stats['lost']} RP", inline=True)
    embed.add_field(name="Mevcut RP", value=f"**{stats['current_rp']}**", inline=True)

    await ctx.send(embed=embed)


@bot.command(name="h10")
async def cmd_h10(ctx):
    stats = get_rp_stats(hours=10)
    net = stats["net_change"]
    emoji = "🟢" if net > 0 else ("🔴" if net < 0 else "⚪")
    sign = "+" if net > 0 else ""

    embed = discord.Embed(title="⏰ Son 10 Saat RP Değişimi", color=0x6ea9ff, timestamp=datetime.utcnow())
    embed.add_field(name="Net Değişim", value=f"**{sign}{net}** RP {emoji}", inline=True)
    embed.add_field(name="Kazanılan", value=f"+{stats['gained']} RP", inline=True)
    embed.add_field(name="Kaybedilen", value=f"-{stats['lost']} RP", inline=True)
    embed.add_field(name="Mevcut RP", value=f"**{stats['current_rp']}**", inline=True)

    await ctx.send(embed=embed)


@bot.command(name="h12")
async def cmd_h12(ctx):
    stats = get_rp_stats(hours=12)
    net = stats["net_change"]
    emoji = "🟢" if net > 0 else ("🔴" if net < 0 else "⚪")
    sign = "+" if net > 0 else ""

    embed = discord.Embed(title="⏰ Son 12 Saat RP Değişimi", color=0x6ea9ff, timestamp=datetime.utcnow())
    embed.add_field(name="Net Değişim", value=f"**{sign}{net}** RP {emoji}", inline=True)
    embed.add_field(name="Kazanılan", value=f"+{stats['gained']} RP", inline=True)
    embed.add_field(name="Kaybedilen", value=f"-{stats['lost']} RP", inline=True)
    embed.add_field(name="Mevcut RP", value=f"**{stats['current_rp']}**", inline=True)

    await ctx.send(embed=embed)


@bot.command(name="h24")
async def cmd_h24(ctx):
    stats = get_rp_stats(hours=24)
    net = stats["net_change"]
    emoji = "🟢" if net > 0 else ("🔴" if net < 0 else "⚪")
    sign = "+" if net > 0 else ""

    embed = discord.Embed(title="⏰ Son 24 Saat RP Değişimi", color=0x6ea9ff, timestamp=datetime.utcnow())
    embed.add_field(name="Net Değişim", value=f"**{sign}{net}** RP {emoji}", inline=True)
    embed.add_field(name="Kazanılan", value=f"+{stats['gained']} RP", inline=True)
    embed.add_field(name="Kaybedilen", value=f"-{stats['lost']} RP", inline=True)
    embed.add_field(name="Mevcut RP", value=f"**{stats['current_rp']}**", inline=True)

    await ctx.send(embed=embed)


@bot.command(name="day")
async def cmd_day(ctx):
    stats = get_rp_stats(today=True)
    net = stats["net_change"]
    emoji = "🟢" if net > 0 else ("🔴" if net < 0 else "⚪")
    sign = "+" if net > 0 else ""

    embed = discord.Embed(title="📅 Gün İçi RP Değişimi", color=0x6ea9ff, timestamp=datetime.utcnow())
    embed.add_field(name="Net Değişim", value=f"**{sign}{net}** RP {emoji}", inline=True)
    embed.add_field(name="Kazanılan", value=f"+{stats['gained']} RP", inline=True)
    embed.add_field(name="Kaybedilen", value=f"-{stats['lost']} RP", inline=True)
    embed.add_field(name="Mevcut RP", value=f"**{stats['current_rp']}**", inline=True)

    await ctx.send(embed=embed)


@bot.command(name="yardim")
async def cmd_help(ctx):
    embed = discord.Embed(
        title="📖 Apex Tracker Bot — Yardım",
        description="Apex Legends istatistiklerinizi Discord'dan sorgulayın.",
        color=0xeb4d4d,
        timestamp=datetime.utcnow()
    )

    commands = {
        "!rp": "Mevcut RP'yi gösterir",
        "!rank": "Mevcut rank'ı gösterir",
        "!stats": "Bugünkü istatistikleri gösterir",
        "!history": "Son 5 değişikliği gösterir",
        "!status": "Tracker durumunu gösterir",
        "!h4": "Son 4 saatteki RP değişimini gösterir",
        "!h10": "Son 10 saatteki RP değişimini gösterir",
        "!h12": "Son 12 saatteki RP değişimini gösterir",
        "!h24": "Son 24 saatteki RP değişimini gösterir",
        "!day": "Gün içindeki RP değişimini gösterir",
        "!yardim": "Bu yardım menüsünü gösterir"
    }

    for cmd, desc in commands.items():
        embed.add_field(name=cmd, value=desc, inline=False)

    await ctx.send(embed=embed)


# =========================================================
# ANA PROGRAM
# =========================================================

def run_bot():
    """Discord botunu ayrı bir thread'de çalıştır."""
    if not DISCORD_BOT_TOKEN:
        logger.error("DISCORD_BOT_TOKEN tanımlı değil!")
        return

    logger.info("Discord Bot başlatılıyor...")
    bot.run(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    init_database()

    # Discord botu ayrı bir thread'de başlat
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    # Otomatik takip başlat
    tracker_thread = threading.Thread(target=automatic_tracker, daemon=True)
    tracker_thread.start()

    logger.info("Apex Tracker başlatıldı - http://127.0.0.1:5000")
    notify_tracker_started()

    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
