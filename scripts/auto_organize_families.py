import sqlite3
import shutil
import os
from datetime import datetime

db_url = os.environ.get("DATABASE_URL")
if db_url and db_url.startswith("sqlite:///"):
    db_path = db_url.replace("sqlite:///", "")
    if db_path.startswith("/"):
        DB_PATH = db_path
    else:
        DB_PATH = os.path.abspath(db_path)
else:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.basename(script_dir) == "scripts":
        BASE_DIR = os.path.dirname(script_dir)
    else:
        BASE_DIR = script_dir
    DB_PATH = os.path.join(BASE_DIR, "data", "family.db")

BACKUP_DIR = os.path.join(os.path.dirname(DB_PATH), "backups")

def backup_db():
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"family_backup_before_organize_{timestamp}.db")
    shutil.copy2(DB_PATH, backup_path)
    print(f"Database backed up to: {backup_path}")

def main():
    backup_db()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # 1. Update primary family group ID 1 (陳氏宗族 -> 王氏家族)
    cursor.execute("""
        UPDATE familygroup 
        SET name = '王氏家族', surname = '王', site_title = '王氏家族家谱', 
            cover_kicker = 'WANG CLAN', subtitle = '王氏支系', root_member_id = 1, is_primary = 1
        WHERE id = 1
    """)
    print("Renamed primary family group to 王氏家族")
    
    # 2. Insert other family groups if they don't exist
    families = [
        (2, "孙氏家族", "孙", "孙氏家族家谱", "SUN CLAN", "孙氏支系", 8),
        (3, "顾氏家族", "顾", "顾氏家族家谱", "GU CLAN", "顾氏支系", 11),
        (4, "曹氏家族", "曹", "曹氏家族家谱", "CAO CLAN", "曹氏支系", 14),
        (5, "周氏家族", "周", "周氏家族家谱", "ZHOU CLAN", "周氏支系", 18),
        (6, "季氏家族", "季", "季氏家族家谱", "JI CLAN", "季氏支系", 19),
        (7, "成氏家族", "成", "成氏家族家谱", "CHENG CLAN", "成氏支系", 23),
        (8, "洪氏家族", "洪", "洪氏家族家谱", "HONG CLAN", "洪氏支系", 30),
        (9, "张氏家族", "张", "张氏家族家谱", "ZHANG CLAN", "张氏支系", 33)
    ]
    
    for fid, name, surname, title, kicker, subtitle, root_id in families:
        cursor.execute("SELECT id FROM familygroup WHERE id = ?", (fid,))
        if cursor.fetchone():
            cursor.execute("""
                UPDATE familygroup 
                SET name = ?, surname = ?, site_title = ?, cover_kicker = ?, subtitle = ?, root_member_id = ?, is_primary = 0
                WHERE id = ?
            """, (name, surname, title, kicker, subtitle, root_id, fid))
        else:
            cursor.execute("""
                INSERT INTO familygroup (id, name, surname, site_title, cover_kicker, subtitle, root_member_id, is_primary, is_active, sort_order, primary_line, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, 1, 0, 'paternal', datetime('now'), datetime('now'))
            """, (fid, name, surname, title, kicker, subtitle, root_id))
        print(f"Prepared family group: {name}")

    # 3. Define member mapping
    # Maps member ID to primary_family_id
    member_primary_family = {
        # 王氏家族 (1)
        1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 7: 1, 13: 1, 15: 1, 17: 1, 28: 1, 29: 1, 36: 1, 37: 1,
        # 孙氏家族 (2)
        8: 2, 9: 2, 20: 2, 21: 2, 22: 2, 6: 2, 31: 2, 25: 2, 26: 2, 39: 2, 41: 2,
        # 顾氏家族 (3)
        11: 3, 12: 3, 10: 3, 27: 3, 40: 3,
        # 曹氏家族 (4)
        14: 4, 16: 4,
        # 周氏家族 (5)
        18: 5, 34: 5,
        # 季氏家族 (6)
        19: 6, 35: 6,
        # 成氏家族 (7)
        23: 7, 24: 7, 38: 7,
        # 洪氏家族 (8)
        30: 8, 32: 8,
        # 张氏家族 (9)
        33: 9
    }
    
    # Update member primary family IDs
    for mid, fid in member_primary_family.items():
        cursor.execute("UPDATE member SET primary_family_id = ? WHERE id = ?", (fid, mid))
    print("Updated primary_family_id for all 41 members")
    
    # 4. Clear all existing records in memberfamilylink
    cursor.execute("DELETE FROM memberfamilylink")
    print("Cleared memberfamilylink table")
    
    # 5. Insert primary links
    for mid, fid in member_primary_family.items():
        cursor.execute("""
            INSERT INTO memberfamilylink (member_id, family_id, relation_type, is_primary, created_at)
            VALUES (?, ?, 'primary', 1, datetime('now'))
        """, (mid, fid))
    print("Inserted primary family links")
    
    # 6. Insert secondary links (spouses marrying into other families)
    secondary_links = [
        (6, 1),   # 孙永芳 (primary 2) -> 王氏家族 (1)
        (10, 1),  # 顾福梅 (primary 3) -> 王氏家族 (1)
        (14, 1),  # 曹福彬 (primary 4) -> 王氏家族 (1)
        (18, 1),  # 周宇飞 (primary 5) -> 王氏家族 (1)
        (19, 4),  # 季小磊 (primary 6) -> 曹氏家族 (4)
        (23, 2),  # 成德泉 (primary 7) -> 孙氏家族 (2)
        (27, 2),  # 顾亚红 (primary 3) -> 孙氏家族 (2)
        (30, 1),  # 洪建国 (primary 8) -> 王氏家族 (1)
        (33, 8),  # 张佳杰 (primary 9) -> 洪氏家族 (8)
        (36, 7),  # 王俊 (primary 1) -> 成氏家族 (7)
        (41, 3),  # 孙建 (primary 2) -> 顾氏家族 (3)
    ]
    
    for mid, fid in secondary_links:
        # Check if link already exists (e.g. if we accidentally put primary here)
        cursor.execute("SELECT id FROM memberfamilylink WHERE member_id = ? AND family_id = ?", (mid, fid))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO memberfamilylink (member_id, family_id, relation_type, is_primary, created_at)
                VALUES (?, ?, 'secondary', 0, datetime('now'))
            """, (mid, fid))
            print(f"Inserted secondary family link: Member {mid} -> Family {fid}")
            
    conn.commit()
    conn.close()
    print("Database organization completed successfully!")

if __name__ == "__main__":
    main()
