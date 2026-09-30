"""
Apex Tracker - Ortak Modül
Tüm API, veritabanı ve değişiklik tespit fonksiyonları burada.
"""
import os
import sqlite3
import requests
import logging
from datetime import datetime, timedelta

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

# =========================================================
# AYARLAR
# =========================================================

API_KEY = os.getenv("APEX_API_KEY", "fca5a99a6765357e766dc4f5e968b293")
UID = os.getenv("APEX_UID", "1010325481639")
PLATFORM = os.getenv("APEX_PLATFORM", "PC")

DB_NAME = os.getenv("APEX_DB_NAME", "apex_tracker.db")

# 45 saniyede bir kontrol
AUTO_CHECK_INTERVAL = int(os.getenv("APEX_CHECK_INTERVAL", "45"))

# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("tracker.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# =========================================================
# VERİTABANI
# =========================================================

def init_database():
    """Veritabanını başlat ve tabloları oluştur."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS player_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT NOT NULL,
            platform TEXT NOT NULL,
            name TEXT,
            level INTEGER,
            rank_name TEXT,
            rank_div INTEGER,
            rank_score INTEGER,
            recorded_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT NOT NULL,
            change_type TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            difference INTEGER,
            recorded_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()
    logger.info("Veritabanı başlatıldı")


def get_latest():
    """Son oyuncu kaydını getir."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM player_history
        WHERE uid = ?
        ORDER BY id DESC
        LIMIT 1
    """, (UID,))

    result = cursor.fetchone()
    conn.close()
    return result


def get_history(limit=50):
    """Oyuncu geçmişini getir."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM player_history
        WHERE uid = ?
        ORDER BY id DESC
        LIMIT ?
    """, (UID, limit))

    results = cursor.fetchall()
    conn.close()
    return results


def get_changes(limit=20):
    """Değişiklik geçmişini getir."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM changes
        WHERE uid = ?
        ORDER BY id DESC
        LIMIT ?
    """, (UID, limit))

    results = cursor.fetchall()
    conn.close()
    return results


def save_change(change_type, old_value, new_value, difference=None):
    """Değişiklik kaydet."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO changes (uid, change_type, old_value, new_value, difference, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        UID,
        change_type,
        str(old_value) if old_value is not None else None,
        str(new_value) if new_value is not None else None,
        difference,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()


def save_player(data):
    """Oyuncu verisini kaydet."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO player_history (uid, platform, name, level, rank_name, rank_div, rank_score, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["uid"],
        data["platform"],
        data["name"],
        data["level"],
        data["rank_name"],
        data["rank_div"],
        data["rank_score"],
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()


# =========================================================
# API
# =========================================================

def get_player_data():
    """API'den oyuncu verilerini al."""
    url = (
        "https://api.apexlegendsstatus.com/bridge"
        f"?auth={API_KEY}"
        f"&uid={UID}"
        f"&platform={PLATFORM}"
    )

    response = requests.get(url, timeout=15)
    response.raise_for_status()

    data = response.json()
    global_data = data.get("global", {})
    rank = global_data.get("rank", {})

    return {
        "uid": UID,
        "platform": PLATFORM,
        "name": global_data.get("name"),
        "level": global_data.get("level"),
        "rank_name": rank.get("rankName"),
        "rank_div": rank.get("rankDiv"),
        "rank_score": rank.get("rankScore")
    }


# =========================================================
# YARDIMCILAR
# =========================================================

def format_rank(data):
    """Rank bilgisini formatla."""
    if not data:
        return "Bilinmiyor"

    name = data["rank_name"] or ""
    division = data["rank_div"]

    if division is not None:
        return f"{name} {division}"
    return name


def detect_changes(old, new):
    """Değişiklikleri tespit et ve kaydet."""
    changes_found = []

    if old is None:
        return changes_found

    # LEVEL
    old_level = old["level"]
    new_level = new["level"]

    if old_level is not None and new_level is not None and old_level != new_level:
        difference = new_level - old_level
        save_change("LEVEL", old_level, new_level, difference)
        changes_found.append(f"LEVEL: {old_level} → {new_level}")

    # RP
    old_rp = old["rank_score"]
    new_rp = new["rank_score"]

    if old_rp is not None and new_rp is not None and old_rp != new_rp:
        difference = new_rp - old_rp
        save_change("RP", old_rp, new_rp, difference)

        if difference > 0:
            changes_found.append(f"RP: +{difference}")
        else:
            changes_found.append(f"RP: {difference}")

    # RANK
    old_rank = format_rank(old)
    new_rank = format_rank(new)

    if old_rank != new_rank:
        save_change("RANK", old_rank, new_rank, None)
        changes_found.append(f"RANK: {old_rank} → {new_rank}")

    # İSİM
    old_name = old["name"]
    new_name = new["name"]

    if old_name and new_name and old_name != new_name:
        save_change("NAME", old_name, new_name, None)
        changes_found.append(f"İSİM: {old_name} → {new_name}")

    return changes_found


def data_changed(old, new):
    """Veri gerçekten değişmiş mi kontrol et."""
    if old is None:
        return True

    return (
        old["name"] != new["name"]
        or old["level"] != new["level"]
        or old["rank_name"] != new["rank_name"]
        or old["rank_div"] != new["rank_div"]
        or old["rank_score"] != new["rank_score"]
    )


# =========================================================
# İSTATİSTİKLER
# =========================================================

def calculate_rp_change():
    """Son RP değişimini hesapla."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT difference FROM changes
        WHERE uid = ? AND change_type = 'RP'
        ORDER BY id DESC
        LIMIT 1
    """, (UID,))

    result = cursor.fetchone()
    conn.close()

    return result["difference"] if result else 0


def get_rp_stats(hours=None, today=False):
    """RP istatistiklerini hesapla."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    now = datetime.now()

    if today:
        start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        start_time = now - timedelta(hours=hours)

    start_string = start_time.strftime("%Y-%m-%d %H:%M:%S")

    # Dönem başlamadan önceki son RP
    cursor.execute("""
        SELECT rank_score FROM player_history
        WHERE uid = ? AND recorded_at < ? AND rank_score IS NOT NULL
        ORDER BY id DESC LIMIT 1
    """, (UID, start_string))
    before_period = cursor.fetchone()

    # Dönem içerisindeki son kayıt
    cursor.execute("""
        SELECT rank_score FROM player_history
        WHERE uid = ? AND recorded_at >= ? AND rank_score IS NOT NULL
        ORDER BY id DESC LIMIT 1
    """, (UID, start_string))
    latest_period = cursor.fetchone()

    if before_period:
        starting_rp = before_period["rank_score"]
    else:
        cursor.execute("""
            SELECT rank_score FROM player_history
            WHERE uid = ? AND recorded_at >= ? AND rank_score IS NOT NULL
            ORDER BY id ASC LIMIT 1
        """, (UID, start_string))
        first_record = cursor.fetchone()
        starting_rp = first_record["rank_score"] if first_record else None

    latest_overall = get_latest()
    current_rp = latest_overall["rank_score"] if latest_overall else None

    # Dönemdeki RP değişiklikleri
    cursor.execute("""
        SELECT difference FROM changes
        WHERE uid = ? AND change_type = 'RP' AND recorded_at >= ?
    """, (UID, start_string))
    rp_changes = cursor.fetchall()

    gained = 0
    lost = 0

    for change in rp_changes:
        difference = change["difference"]
        if difference is None:
            continue
        if difference > 0:
            gained += difference
        elif difference < 0:
            lost += abs(difference)

    net_change = (current_rp - starting_rp) if (starting_rp is not None and current_rp is not None) else 0

    conn.close()

    return {
        "starting_rp": starting_rp,
        "current_rp": current_rp,
        "net_change": net_change,
        "gained": gained,
        "lost": lost
    }


def get_weekly_trends():
    """Haftalık RP trendlerini hesapla (yeni grafik için)."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    now = datetime.now()
    week_ago = now - timedelta(days=7)

    cursor.execute("""
        SELECT rank_score, recorded_at FROM player_history
        WHERE uid = ? AND recorded_at >= ? AND rank_score IS NOT NULL
        ORDER BY id ASC
    """, (UID, week_ago.strftime("%Y-%m-%d %H:%M:%S")))

    results = cursor.fetchall()
    conn.close()

    return [{"rp": r["rank_score"], "date": r["recorded_at"]} for r in results]


def get_rank_distribution():
    """Rank dağılımını hesapla (yeni grafik için)."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT rank_name, COUNT(*) as count FROM player_history
        WHERE uid = ? AND rank_name IS NOT NULL
        GROUP BY rank_name
        ORDER BY count DESC
    """, (UID,))

    results = cursor.fetchall()
    conn.close()

    return [{"rank": r["rank_name"], "count": r["count"]} for r in results]


def get_daily_rp_summary():
    """Günlük RP özetini hesapla (yeni grafik için)."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    now = datetime.now()
    week_ago = now - timedelta(days=7)

    cursor.execute("""
        SELECT 
            date(recorded_at) as day,
            MAX(rank_score) as max_rp,
            MIN(rank_score) as min_rp
        FROM player_history
        WHERE uid = ? AND recorded_at >= ? AND rank_score IS NOT NULL
        GROUP BY date(recorded_at)
        ORDER BY day ASC
    """, (UID, week_ago.strftime("%Y-%m-%d %H:%M:%S")))

    results = cursor.fetchall()
    conn.close()

    return [{"day": r["day"], "max_rp": r["max_rp"], "min_rp": r["min_rp"]} for r in results]
