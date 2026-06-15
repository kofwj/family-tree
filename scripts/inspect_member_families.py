import sqlite3
import os

db_url = os.environ.get("DATABASE_URL")
if db_url and db_url.startswith("sqlite:///"):
    db_path = db_url.replace("sqlite:///", "")
    if not db_path.startswith("/"):
        db_path = os.path.abspath(db_path)
else:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.basename(script_dir) == "scripts":
        BASE_DIR = os.path.dirname(script_dir)
    else:
        BASE_DIR = script_dir
    db_path = os.path.join(BASE_DIR, "data", "family.db")

print(f"Opening database: {db_path}")
if not os.path.exists(db_path):
    print("Database file not found!")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. Print family groups
print("\n=== Family Groups ===")
cursor.execute("SELECT id, name, surname, is_primary, is_active FROM familygroup")
families = cursor.fetchall()
for f in families:
    print(f"ID: {f[0]}, Name: {f[1]}, Surname: {f[2]}, Is Primary: {f[3]}, Is Active: {f[4]}")

# 2. Count members grouped by primary_family_id
print("\n=== Member Counts grouped by primary_family_id ===")
cursor.execute("SELECT primary_family_id, COUNT(*) FROM member GROUP BY primary_family_id")
rows = cursor.fetchall()
for r in rows:
    print(f"Primary Family ID: {r[0]}, Count: {r[1]}")

# 3. Print count of links grouped by family_id
print("\n=== MemberFamilyLink Counts grouped by family_id ===")
cursor.execute("SELECT family_id, COUNT(*) FROM memberfamilylink GROUP BY family_id")
rows = cursor.fetchall()
for r in rows:
    print(f"Family ID: {r[0]}, Count: {r[1]}")

# 4. Print all members with primary_family_id
print("\n=== Sample of members ===")
cursor.execute("SELECT id, name, primary_family_id FROM member LIMIT 10")
members = cursor.fetchall()
for m in members:
    print(f"ID: {m[0]}, Name: {m[1]}, Primary Family ID: {m[2]}")

conn.close()
