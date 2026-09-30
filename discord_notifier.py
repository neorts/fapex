"""
Apex Tracker - Discord Bildirim Modülü
Rank değişimi, RP değişimi ve hata durumlarında Discord'a bildirim gönderir.
"""
import os
import requests
import logging
from datetime import datetime

# .env dosyasını manuel oku
def load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())

load_env()

logger = logging.getLogger(__name__)

# Discord webhook URL'si
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# Bildirim eşikleri
RP_ALERT_THRESHOLD = 0         # Tüm RP değişimlerinde bildirim
RANK_CHANGE_ALERT = True       # Rank değişiminde bildirim
LEVEL_CHANGE_ALERT = True      # Level değişiminde bildirim
ERROR_ALERT = True             # API hatalarında bildirim


def send_discord_notification(title, description, color=0xeb4d4d, fields=None):
    """Discord'a embed mesaj gönder."""
    if not DISCORD_WEBHOOK_URL:
        logger.warning("Discord webhook URL tanımlı değil, bildirim atlandı")
        return False

    embed = {
        "title": title,
        "description": description,
        "color": color,
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {
            "text": "Apex Tracker"
        }
    }

    if fields:
        embed["fields"] = fields

    payload = {
        "embeds": [embed]
    }

    try:
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        logger.info(f"Discord bildirimi gönderildi: {title}")
        return True
    except Exception as e:
        logger.error(f"Discord bildirimi gönderilemedi: {e}")
        return False


def notify_rp_change(old_rp, new_rp, player_name, rank_name):
    """RP değişimi bildirimi gönder."""
    difference = new_rp - old_rp

    # Tüm değişimler bildirilir (eşik yok)

    if difference > 0:
        title = f"🎮 RP Kazancı! +{difference}"
        color = 0x43d17a  # Yeşil
        description = f"**{player_name}** {difference} RP kazandı!"
    else:
        title = f"💔 RP Kaybı {difference}"
        color = 0xef6464  # Kırmızı
        description = f"**{player_name}** {abs(difference)} RP kaybetti!"

    fields = [
        {"name": "Rank", "value": rank_name, "inline": True},
        {"name": "Eski RP", "value": str(old_rp), "inline": True},
        {"name": "Yeni RP", "value": str(new_rp), "inline": True},
        {"name": "Değişim", "value": f"{difference:+d} RP", "inline": True}
    ]

    return send_discord_notification(title, description, color, fields)


def notify_rank_change(old_rank, new_rank, player_name, current_rp):
    """Rank değişimi bildirimi gönder."""
    if not RANK_CHANGE_ALERT:
        return False

    # Yükselme mi düşme mi?
    rank_order = ["Bronze", "Silver", "Gold", "Platinum", "Diamond", "Master", "Apex Predator"]

    old_idx = rank_order.index(old_rank.split()[0]) if old_rank.split()[0] in rank_order else -1
    new_idx = rank_order.index(new_rank.split()[0]) if new_rank.split()[0] in rank_order else -1

    if new_idx > old_idx:
        title = f"🏆 RANK YÜKSELDİ!"
        color = 0xb98cff  # Mor
        description = f"**{player_name}** yeni rankına yükseldi!"
    else:
        title = f"📉 Rank Düşüşü"
        color = 0xef6464  # Kırmızı
        description = f"**{player_name}** rankı düştü!"

    fields = [
        {"name": "Eski Rank", "value": old_rank, "inline": True},
        {"name": "Yeni Rank", "value": new_rank, "inline": True},
        {"name": "Mevcut RP", "value": str(current_rp), "inline": True}
    ]

    return send_discord_notification(title, description, color, fields)


def notify_level_change(old_level, new_level, player_name):
    """Level değişimi bildirimi gönder."""
    if not LEVEL_CHANGE_ALERT:
        return False

    title = f"⬆️ Level Atladı!"
    color = 0x6ea9ff  # Mavi
    description = f"**{player_name}** level atladı!"

    fields = [
        {"name": "Eski Level", "value": str(old_level), "inline": True},
        {"name": "Yeni Level", "value": str(new_level), "inline": True}
    ]

    return send_discord_notification(title, description, color, fields)


def notify_api_error(error_message):
    """API hatası bildirimi gönder."""
    if not ERROR_ALERT:
        return False

    title = "⚠️ API Hatası"
    color = 0xffa500  # Turuncu
    description = f"Apex Tracker API hatası:\n```\n{error_message}\n```"

    return send_discord_notification(title, description, color)


def notify_tracker_started():
    """Tracker başlatıldığında bildirim gönder."""
    title = "🚀 Apex Tracker Başlatıldı"
    color = 0x43d17a  # Yeşil
    description = "Otomatik takip sistemi aktif!"

    return send_discord_notification(title, description, color)


def notify_tracker_stopped():
    """Tracker durdurulduğunda bildirim gönder."""
    title = "🛑 Apex Tracker Durduruldu"
    color = 0xef6464  # Kırmızı
    description = "Otomatik takip sistemi pasif!"

    return send_discord_notification(title, description, color)
