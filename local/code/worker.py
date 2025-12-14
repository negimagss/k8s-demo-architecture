import pika
import psycopg2
import os
import time
import json
import sys

# --- Configuration ---
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
        print(f"Error connecting to DB: {e}")
        return None

def init_db():
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    content TEXT NOT NULL,
                    owner TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
        conn.close()
        print("Database initialized.")

def callback(ch, method, properties, body):
    message_data = json.loads(body)
    content = message_data.get('content')
    owner = message_data.get('owner')
    print(f"Received: {content}")
    
    # Log to file for debugging
    with open("/tmp/worker.log", "a") as f:
        f.write(f"Received message: {content}\n")

    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO messages (content, owner) VALUES (%s, %s)",
                    (content, owner)
                )
                conn.commit()
                print("Saved to DB")
        except Exception as e:
            print(f"Error saving to DB: {e}")
        finally:
            conn.close()
    
    ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    print("Worker starting...")
    # Wait for services (simple retry logic)
    time.sleep(10)
    init_db()

    # Connect to RabbitMQ
    while True:
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=RABBITMQ_HOST)
            )
            channel = connection.channel()
            channel.queue_declare(queue='task_queue', durable=True)

            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue='task_queue', on_message_callback=callback)

            print('Waiting for messages...')
            channel.start_consuming()
        except Exception as e:
            print(f"Connection failed, retrying in 5s: {e}")
            time.sleep(5)

if __name__ == '__main__':
    main()
