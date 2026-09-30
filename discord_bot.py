"""
Apex Tracker - Discord Bot
Discord'dan komut alıp veritabanından cevap verir.
"""
import os
import discord
from discord.ext import commands
from datetime import datetime

from tracker_core import (
    get_latest, get_history, get_changes,
    format_rank, calculate_rp_change, get_rp_stats,
    get_weekly_trends, get_rank_distribution, get_daily_rp_summary,
    logger, load_env
)

load_env()

# Bot ayarları
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
COMMAND_PREFIX = "!"

# Discord intents
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)


@bot.event
async def on_ready():
    """Bot hazır olduğunda çağrılır."""
    logger.info(f"Discord Bot hazır: {bot.user.name} ({bot.user.id})")
    print(f"Bot hazır: {bot.user.name}")
    print(f"Komut ön eki: {COMMAND_PREFIX}")
    print(f"Örnek: {COMMAND_PREFIX}rp")


@bot.command(name="rp")
async def cmd_rp(ctx):
    """Mevcut RP'yi gösterir."""
    player = get_latest()
    if not player:
        await ctx.send("❌ Henüz veri yok. Tracker'ın çalıştığından emin olun.")
        return

    embed = discord.Embed(
        title="🎮 Mevcut RP",
        color=0xeb4d4d,
        timestamp=datetime.utcnow()
    )
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
    """Mevcut rank'ı gösterir."""
    player = get_latest()
    if not player:
        await ctx.send("❌ Henüz veri yok.")
        return

    embed = discord.Embed(
        title="🏆 Mevcut Rank",
        color=0xb98cff,
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Oyuncu", value=player["name"], inline=True)
    embed.add_field(name="Rank", value=format_rank(player), inline=True)
    embed.add_field(name="RP", value=f"**{player['rank_score']}**", inline=True)
    embed.add_field(name="Level", value=str(player["level"]), inline=True)

    await ctx.send(embed=embed)


@bot.command(name="stats")
async def cmd_stats(ctx):
    """Bugünkü istatistikleri gösterir."""
    daily = get_rp_stats(today=True)
    stats_24h = get_rp_stats(hours=24)
    stats_1h = get_rp_stats(hours=1)

    embed = discord.Embed(
        title="📊 İstatistikler",
        color=0x6ea9ff,
        timestamp=datetime.utcnow()
    )

    # Bugün
    embed.add_field(
        name="📅 Bugün",
        value=(
            f"Net: **{daily['net_change']:+d}** RP\n"
            f"Kazanılan: **+{daily['gained']}** RP\n"
            f"Kaybedilen: **-{daily['lost']}** RP"
        ),
        inline=True
    )

    # Son 24 saat
    embed.add_field(
        name="⏰ Son 24 Saat",
        value=(
            f"Net: **{stats_24h['net_change']:+d}** RP\n"
            f"Kazanılan: **+{stats_24h['gained']}** RP\n"
            f"Kaybedilen: **-{stats_24h['lost']}** RP"
        ),
        inline=True
    )

    # Son 1 saat
    embed.add_field(
        name="⏱️ Son 1 Saat",
        value=(
            f"Net: **{stats_1h['net_change']:+d}** RP\n"
            f"Kazanılan: **+{stats_1h['gained']}** RP\n"
            f"Kaybedilen: **-{stats_1h['lost']}** RP"
        ),
        inline=True
    )

    await ctx.send(embed=embed)


@bot.command(name="history")
async def cmd_history(ctx):
    """Son 5 değişikliği gösterir."""
    changes = get_changes(5)

    if not changes:
        await ctx.send("❌ Henüz değişiklik kaydı yok.")
        return

    embed = discord.Embed(
        title="📜 Son Değişiklikler",
        color=0xeb4d4d,
        timestamp=datetime.utcnow()
    )

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

        embed.add_field(
            name=f"{change_type} — {date}",
            value=value,
            inline=False
        )

    await ctx.send(embed=embed)


@bot.command(name="status")
async def cmd_status(ctx):
    """Tracker durumunu gösterir."""
    from app import tracker_status, AUTO_CHECK_INTERVAL

    embed = discord.Embed(
        title="⚙️ Tracker Durumu",
        color=0x43d17a,
        timestamp=datetime.utcnow()
    )

    status = "🟢 Aktif" if tracker_status["active"] else "🔴 Pasif"
    embed.add_field(name="Durum", value=status, inline=True)
    embed.add_field(name="Kontrol Aralığı", value=f"{AUTO_CHECK_INTERVAL} saniye", inline=True)

    if tracker_status["last_check"]:
        embed.add_field(
            name="Son Kontrol",
            value=tracker_status["last_check"].strftime("%Y-%m-%d %H:%M:%S"),
            inline=True
        )

    if tracker_status["last_success"]:
        embed.add_field(
            name="Son Başarılı",
            value=tracker_status["last_success"].strftime("%Y-%m-%d %H:%M:%S"),
            inline=True
        )

    if tracker_status["next_check"]:
        embed.add_field(
            name="Sonraki Kontrol",
            value=tracker_status["next_check"].strftime("%Y-%m-%d %H:%M:%S"),
            inline=True
        )

    if tracker_status["last_error"]:
        embed.add_field(
            name="Son Hata",
            value=tracker_status["last_error"],
            inline=False
        )

    await ctx.send(embed=embed)


@bot.command(name="h4")
async def cmd_h4(ctx):
    """Son 4 saatteki toplam RP değişimini gösterir."""
    stats = get_rp_stats(hours=4)
    net = stats["net_change"]

    if net > 0:
        emoji = "🟢"
        sign = "+"
    elif net < 0:
        emoji = "🔴"
        sign = ""
    else:
        emoji = "⚪"
        sign = ""

    embed = discord.Embed(
        title="⏱️ Son 4 Saat RP Değişimi",
        color=0x6ea9ff,
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Net Değişim", value=f"**{sign}{net}** RP {emoji}", inline=True)
    embed.add_field(name="Kazanılan", value=f"+{stats['gained']} RP", inline=True)
    embed.add_field(name="Kaybedilen", value=f"-{stats['lost']} RP", inline=True)
    embed.add_field(name="Mevcut RP", value=f"**{stats['current_rp']}**", inline=True)

    await ctx.send(embed=embed)


@bot.command(name="h10")
async def cmd_h10(ctx):
    """Son 10 saatteki toplam RP değişimini gösterir."""
    stats = get_rp_stats(hours=10)
    net = stats["net_change"]

    if net > 0:
        emoji = "🟢"
        sign = "+"
    elif net < 0:
        emoji = "🔴"
        sign = ""
    else:
        emoji = "⚪"
        sign = ""

    embed = discord.Embed(
        title="⏰ Son 10 Saat RP Değişimi",
        color=0x6ea9ff,
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Net Değişim", value=f"**{sign}{net}** RP {emoji}", inline=True)
    embed.add_field(name="Kazanılan", value=f"+{stats['gained']} RP", inline=True)
    embed.add_field(name="Kaybedilen", value=f"-{stats['lost']} RP", inline=True)
    embed.add_field(name="Mevcut RP", value=f"**{stats['current_rp']}**", inline=True)

    await ctx.send(embed=embed)


@bot.command(name="h12")
async def cmd_h12(ctx):
    """Son 12 saatteki toplam RP değişimini gösterir."""
    stats = get_rp_stats(hours=12)
    net = stats["net_change"]

    if net > 0:
        emoji = "🟢"
        sign = "+"
    elif net < 0:
        emoji = "🔴"
        sign = ""
    else:
        emoji = "⚪"
        sign = ""

    embed = discord.Embed(
        title="⏰ Son 12 Saat RP Değişimi",
        color=0x6ea9ff,
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Net Değişim", value=f"**{sign}{net}** RP {emoji}", inline=True)
    embed.add_field(name="Kazanılan", value=f"+{stats['gained']} RP", inline=True)
    embed.add_field(name="Kaybedilen", value=f"-{stats['lost']} RP", inline=True)
    embed.add_field(name="Mevcut RP", value=f"**{stats['current_rp']}**", inline=True)

    await ctx.send(embed=embed)


@bot.command(name="h24")
async def cmd_h24(ctx):
    """Son 24 saatteki toplam RP değişimini gösterir."""
    stats = get_rp_stats(hours=24)
    net = stats["net_change"]

    if net > 0:
        emoji = "🟢"
        sign = "+"
    elif net < 0:
        emoji = "🔴"
        sign = ""
    else:
        emoji = "⚪"
        sign = ""

    embed = discord.Embed(
        title="⏰ Son 24 Saat RP Değişimi",
        color=0x6ea9ff,
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Net Değişim", value=f"**{sign}{net}** RP {emoji}", inline=True)
    embed.add_field(name="Kazanılan", value=f"+{stats['gained']} RP", inline=True)
    embed.add_field(name="Kaybedilen", value=f"-{stats['lost']} RP", inline=True)
    embed.add_field(name="Mevcut RP", value=f"**{stats['current_rp']}**", inline=True)

    await ctx.send(embed=embed)


@bot.command(name="day")
async def cmd_day(ctx):
    """Gün içindeki toplam RP değişimini gösterir."""
    stats = get_rp_stats(today=True)
    net = stats["net_change"]

    if net > 0:
        emoji = "🟢"
        sign = "+"
    elif net < 0:
        emoji = "🔴"
        sign = ""
    else:
        emoji = "⚪"
        sign = ""

    embed = discord.Embed(
        title="📅 Gün İçi RP Değişimi",
        color=0x6ea9ff,
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Net Değişim", value=f"**{sign}{net}** RP {emoji}", inline=True)
    embed.add_field(name="Kazanılan", value=f"+{stats['gained']} RP", inline=True)
    embed.add_field(name="Kaybedilen", value=f"-{stats['lost']} RP", inline=True)
    embed.add_field(name="Mevcut RP", value=f"**{stats['current_rp']}**", inline=True)

    await ctx.send(embed=embed)


@bot.command(name="yardim")
async def cmd_help(ctx):
    """Yardım menüsünü gösterir."""
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
# BAŞLAT
# =========================================================

if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN:
        logger.error("DISCORD_BOT_TOKEN tanımlı değil!")
        print("Hata: DISCORD_BOT_TOKEN .env dosyasında tanımlı değil!")
        exit(1)

    logger.info("Discord Bot başlatılıyor...")
    bot.run(DISCORD_BOT_TOKEN)
