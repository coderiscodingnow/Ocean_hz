import sqlite3
import os

# Path to database
db_path = "ocean_hazard.db"

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

# Connect to database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Check if column already exists
    cursor.execute("PRAGMA table_info(hazard_posts)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'ai_relevance_score' in columns:
        print("✅ Column 'ai_relevance_score' already exists!")
    else:
        # Add the column
        cursor.execute("ALTER TABLE hazard_posts ADD COLUMN ai_relevance_score REAL DEFAULT 0.0")
        conn.commit()
        print("✅ Successfully added 'ai_relevance_score' column to hazard_posts table!")
        
except Exception as e:
    print(f"❌ Error: {e}")
    conn.rollback()
finally:
    conn.close()

print("\n✅ Database migration complete!")
