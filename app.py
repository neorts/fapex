from flask import Flask, render_template, redirect, url_for
from datetime import datetime, timedelta
import threading
import time

from tracker_core import (
    init_database, get_latest, get_history, get_changes,
    get_player_data, save_player, detect_changes, data_changed,
    format_rank, calculate_rp_change, get_rp_stats,
    get_weekly_trends, get_rank_distribution, get_daily_rp_summary,
    logger, DB_NAME, AUTO_CHECK_INTERVAL
)
from discord_notifier import (
    notify_rp_change, notify_rank_change, notify_level_change,
    notify_api_error, notify_tracker_started
)

app = Flask(__name__)

# =========================================================
# TAKİP DURUMU
# =========================================================

tracker_status = {
    "active": True,
    "last_check": None,
    "last_success": None,
    "last_error": None,
    "next_check": None
}

# =========================================================
# OYUNCUYU KONTROL ET
# =========================================================

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

                # Discord bildirimleri - Tüm RP değişimleri bildirilir
                if old_data["rank_score"] is not None and new_data["rank_score"] is not None:
                    if old_data["rank_score"] != new_data["rank_score"]:
                        notify_rp_change(
                            old_data["rank_score"],
                            new_data["rank_score"],
                            new_data["name"],
                            format_rank(new_data)
                        )

                # Rank değişimi
                old_rank = format_rank(old_data)
                new_rank = format_rank(new_data)
                if old_rank != new_rank:
                    notify_rank_change(
                        old_rank,
                        new_rank,
                        new_data["name"],
                        new_data["rank_score"]
                    )

                # Level değişimi
                if old_data["level"] is not None and new_data["level"] is not None:
                    if old_data["level"] != new_data["level"]:
                        notify_level_change(
                            old_data["level"],
                            new_data["level"],
                            new_data["name"]
                        )

            save_player(new_data)
            logger.info(
                f"Kayıt: {new_data['name']} | "
                f"{format_rank(new_data)} | "
                f"{new_data['rank_score']} RP"
            )
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


# =========================================================
# OTOMATİK TAKİP
# =========================================================

def automatic_tracker():
    logger.info("Otomatik takip başladı")
    update_player()

    while True:
        time.sleep(AUTO_CHECK_INTERVAL)
        update_player()


# =========================================================
# ROTALAR
# =========================================================

@app.route("/")
def index():
    player = get_latest()
    history = get_history(30)
    changes = get_changes(20)
    rp_change = calculate_rp_change()

    daily_stats = get_rp_stats(today=True)
    stats_24h = get_rp_stats(hours=24)
    stats_1h = get_rp_stats(hours=1)

    # Yeni grafik verileri
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
    """Discord bildirimini test etmek için test endpoint'i."""
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
    """Bildirim ayarlarını göster."""
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
# BAŞLAT
# =========================================================

if __name__ == "__main__":
    init_database()

    tracker_thread = threading.Thread(target=automatic_tracker, daemon=True)
    tracker_thread.start()

    logger.info("Apex Tracker başlatıldı - http://127.0.0.1:5000")
    notify_tracker_started()

    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
