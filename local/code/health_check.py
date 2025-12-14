import os
import time
import psycopg2
import pika
import sys
from datetime import datetime

# Configuration
APP_NAME = os.environ.get('APP_NAME', 'Unknown-App')
RABBITMQ_HOST = 'rabbitmq-service'
DB_HOST = 'postgres-service'
DB_NAME = os.environ.get('POSTGRES_DB', 'messages_db')
DB_USER = os.environ.get('POSTGRES_USER', 'admin')
DB_PASS = os.environ.get('POSTGRES_PASSWORD', 'adminpassword')

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        return conn
    except Exception as e:
        print(f"[{APP_NAME}] DB Connection Failed: {e}")
        return None

def log_health(status):
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cur:
            # Create table if not exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS health (
                    id SERIAL PRIMARY KEY,
                    app_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Log status
            cur.execute(
                "INSERT INTO health (app_name, status) VALUES (%s, %s)",
                (APP_NAME, status)
            )
            conn.commit()
        conn.close()
        print(f"[{APP_NAME}] Health Logged: {status}")
        return True
    except Exception as e:
        print(f"[{APP_NAME}] Failed to log health: {e}")
        return False

def check_rabbitmq():
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST, connection_attempts=3, retry_delay=2)
        )
        connection.close()
        print(f"[{APP_NAME}] RabbitMQ Connection: OK")
        return True
    except Exception as e:
        print(f"[{APP_NAME}] RabbitMQ Connection Failed: {e}")
        return False

def wait_for_dependency(check_func, name, retries=10, delay=5):
    for i in range(retries):
        if check_func():
            return True
        print(f"[{APP_NAME}] Waiting for {name}... ({i+1}/{retries})")
        time.sleep(delay)
    return False

def check_db():
    conn = get_db_connection()
    if conn:
        conn.close()
        return True
    return False

def main():
    print(f"--- FIT TEST STARTED: {APP_NAME} ---")
    
    # 1. Wait for DB
    if not wait_for_dependency(check_db, "Postgres"):
        print(f"[{APP_NAME}] Failed to connect to Postgres after retries.")
        sys.exit(1)

    # 2. Log Startup
    if not log_health("Starting Up"):
        print(f"[{APP_NAME}] Failed to log startup.")
        sys.exit(1)
    
    # 3. Wait for RabbitMQ
    if not wait_for_dependency(check_rabbitmq, "RabbitMQ"):
        log_health("Failed: RabbitMQ unreachable")
        sys.exit(1)
        
    # 4. Log Success
    if not log_health("Healthy"):
        sys.exit(1)
        
    print(f"--- FIT TEST PASSED: {APP_NAME} ---")
    sys.exit(0)

if __name__ == "__main__":
    main()
