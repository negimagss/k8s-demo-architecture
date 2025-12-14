import http.server
import socketserver
import urllib.parse
from datetime import datetime
import os
import pika
import psycopg2
import json

PORT = 8000

# Service Config
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
    except Exception:
        return None

def publish_message(content, owner):
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()
        channel.queue_declare(queue='task_queue', durable=True)
        
        message = json.dumps({'content': content, 'owner': owner})
        #send data to a queue
        channel.basic_publish(
            exchange='',
            routing_key='task_queue',
            body=message,
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
            ))
        connection.close()
        return True
    except Exception as e:
        print(f"Failed to publish: {e}")
        return False

class MyHandler(http.server.SimpleHTTPRequestHandler):
    def get_template_path(self, filename):
        # 1. Container path
        if os.path.exists(f"/app/{filename}"):
            return f"/app/{filename}"
        # 2. Local path (same dir)
        local_path = os.path.join(os.path.dirname(__file__), filename)
        if os.path.exists(local_path):
            return local_path
        # 3. Local path (html subdir)
        html_subdir_path = os.path.join(os.path.dirname(__file__), "html", filename)
        if os.path.exists(html_subdir_path):
            return html_subdir_path
        # 4. Fallback to just filename
        return filename

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_path.query)

        if parsed_path.path == '/':
            file_path = self.get_template_path("landing.html")
            try:
                with open(file_path, "r") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(content.encode())
            except Exception as e:
                self.send_error(500, f"Error loading landing page: {e}")

        elif parsed_path.path == '/home':
            # Log the visit!
            success = publish_message('Home Page', 'Shardul')
            
            # Allow clean rendering of home/index with default data
            file_path = self.get_template_path("index.html")
            if os.path.exists(file_path):
                with open(file_path, "r") as f:
                    content = f.read()
                
                # Replace placeholders
                content = content.replace("{{DATA}}", "Home Page")
                content = content.replace("{{TIMESTAMP}}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                content = content.replace("{{OWNER}}", os.environ.get('OWNER_NAME', 'Guest'))
                
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(content.encode())
            else:
                self.send_error(404, "Home Template Not Found")

        elif parsed_path.path == '/view':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            conn = get_db_connection()
            rows = []
            health_rows = []
            if conn:
                with conn.cursor() as cur:
                    # 1. Fetch Messages (Limit 10)
                    cur.execute("SELECT to_regclass('public.messages');")
                    if cur.fetchone()[0]:
                        cur.execute("SELECT id, content, owner, timestamp FROM messages ORDER BY id DESC LIMIT 10")
                        rows = cur.fetchall()
                    
                    # 2. Fetch Health Logs (Limit 10)
                    cur.execute("SELECT to_regclass('public.health');")
                    if cur.fetchone()[0]:
                         # Check if column exists
                        try:
                            cur.execute("SELECT id, app_name, status, timestamp, pod_name FROM health ORDER BY id DESC LIMIT 10")
                        except Exception:
                            conn.rollback()
                            cur.execute("SELECT id, app_name, status, timestamp, NULL as pod_name FROM health ORDER BY id DESC LIMIT 10")
                        
                        health_rows = cur.fetchall()
                conn.close()

            html = """
            <html>
            <head>
                <title>Data View</title>
                <style>
                    body { font-family: sans-serif; padding: 20px; background: #f0f0f0; }
                    table { width: 100%; border-collapse: collapse; background: white; margin-bottom: 40px; }
                    th, td { padding: 10px; border: 1px solid #ddd; text-align: left; }
                    th { background: #333; color: white; }
                    h2 { border-bottom: 2px solid #333; padding-bottom: 10px; margin-top: 40px; }
                </style>
            </head>
            <body>
                <h1>Database Inspector</h1>
                <p><a href="/">Back to Home</a></p>
                
                <h2>Stored Messages</h2>
                <table>
                    <tr><th>ID</th><th>Content</th><th>Owner</th><th>Timestamp</th></tr>
            """
            for row in rows:
                html += f"<tr><td>{row[0]}</td><td>{row[1]}</td><td>{row[2]}</td><td>{row[3]}</td></tr>"
            
            html += """
                </table>
                
                <h2>Service Health Logs</h2>
                <table>
                    <tr><th>ID</th><th>App Name</th><th>Status</th><th>Pod Name</th><th>Timestamp</th></tr>
            """
            for row in health_rows:
                status_color = "green" if row[2] == "Healthy" else "orange"
                pod_name = row[4] if row[4] else "N/A"
                html += f"<tr><td>{row[0]}</td><td>{row[1]}</td><td style='color:{status_color}; font-weight:bold;'>{row[2]}</td><td>{pod_name}</td><td>{row[3]}</td></tr>"

            html += "</table></body></html>"
            self.wfile.write(html.encode())

        elif parsed_path.path == '/home':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            try:
                # Render index.html (Default) without saving
                template_path = self.get_template_path("index.html")
                with open(template_path, "r") as template_file:
                    html_content = template_file.read()
                
                # Replace placeholders with default/display values
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                owner_name = os.environ.get('OWNER_NAME', 'Guest')
                
                response_content = html_content.replace("{{DATA}}", "Welcome Home") \
                                               .replace("{{TIMESTAMP}}", timestamp) \
                                               .replace("{{OWNER}}", owner_name)
                self.wfile.write(response_content.encode())
            except Exception as e:
                self.wfile.write(f"Error loading home page: {e}".encode())

        elif parsed_path.path == '/save':
            data_to_save = query_params.get('data', ['Default Data'])[0]
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            owner_name = os.environ.get('OWNER_NAME', 'Unknown Owner')
            
            # Publish to RabbitMQ
            success = publish_message(data_to_save, owner_name)
            
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            # Determine which template to load
            template_param = query_params.get('template', ['default'])[0]
            if template_param == 'space':
                template_file_name = "space.html"
            elif template_param == 'webgl':
                template_file_name = "webgl.html"
            elif template_param == 'architecture':
                template_file_name = "architecture.html"
            else:
                template_file_name = "index.html"

            try:
                template_path = self.get_template_path(template_file_name)
                
                with open(template_path, "r") as template_file:
                    html_content = template_file.read()
                
                response_content = html_content.replace("{{DATA}}", data_to_save) \
                                               .replace("{{TIMESTAMP}}", timestamp) \
                                               .replace("{{OWNER}}", owner_name)
            except Exception as e:
                response_content = f"Error loading template: {e}"

            self.wfile.write(response_content.encode())
        else:
            self.send_error(404, "Not Found")

if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), MyHandler) as httpd:
        print("serving at port", PORT)
        httpd.serve_forever()
