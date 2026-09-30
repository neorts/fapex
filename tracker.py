"""
Apex Tracker - CLI Betiği
Terminal üzerinden otomatik takip yapar.
"""
import time
import logging
from tracker_core import (
    init_database, get_latest, get_player_data, save_player,
    detect_changes, data_changed, format_rank, logger
)

# Kaç saniyede bir kontrol edilecek?
CHECK_INTERVAL = 30


def check_player():
    """Tek seferlik oyuncu kontrolü."""
    logger.info("Oyuncu kontrol ediliyor...")

    try:
        new_data = get_player_data()
        old_data = get_latest()

        if data_changed(new_data, old_data):
            save_player(new_data)

            logger.info("Değişiklik tespit edildi!")
            logger.info(f"Oyuncu: {new_data['name']}")
            logger.info(f"Level: {new_data['level']}")
            logger.info(f"Rank: {format_rank(new_data)}")
            logger.info(f"RP: {new_data['rank_score']}")

        else:
            logger.info(f"Değişiklik yok. RP: {new_data['rank_score']}")

    except Exception as e:
        logger.error(f"API hatası: {e}")


def main():
    """Ana döngü."""
    init_database()

    logger.info("=" * 50)
    logger.info("APEX AUTO TRACKER - CLI")
    logger.info("=" * 50)
    logger.info(f"Kontrol aralığı: {CHECK_INTERVAL} saniye")
    logger.info("")

    while True:
        check_player()
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
