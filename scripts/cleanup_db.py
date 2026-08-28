import sqlite3
import sys
from pathlib import Path

# Add root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

db_path = PROJECT_ROOT / "storage" / "vertex_quotes.db"
if db_path.exists():
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM quotes 
        WHERE id LIKE 'quote_%' 
           OR id LIKE 'test_%' 
           OR quote_code LIKE 'VTX-ATK%' 
           OR quote_code LIKE 'VTX-XSS%' 
           OR quote_code LIKE 'VTX-CONFIDENTIAL%' 
           OR quote_code LIKE 'VTX-SEC%' 
           OR customer_name LIKE '%<script>%' 
           OR customer_name LIKE '%XSS%'
    """)
    cursor.execute("""
        DELETE FROM users 
        WHERE username LIKE 'dealer_competitor%' 
           OR username LIKE 'test_%' 
           OR username LIKE 'dealer_atk%'
           OR full_name LIKE '%Đối Thủ%'
    """)
    conn.commit()
    print("Database cleaned up successfully!")
