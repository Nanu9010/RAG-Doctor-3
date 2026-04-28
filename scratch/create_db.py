import MySQLdb
import os
from dotenv import load_dotenv

load_dotenv('backend/.env')

db_name = os.getenv('DB_NAME', 'doctor_rag_3')
db_user = os.getenv('DB_USER', 'root')
db_pass = os.getenv('DB_PASSWORD', '')
db_host = os.getenv('DB_HOST', '127.0.0.1')
db_port = int(os.getenv('DB_PORT', '3306'))

try:
    conn = MySQLdb.connect(host=db_host, user=db_user, passwd=db_pass, port=db_port)
    cursor = conn.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
    print(f"Database '{db_name}' ensured.")
    conn.close()
except Exception as e:
    print(f"Error: {e}")
