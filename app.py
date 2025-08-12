from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, disconnect
import sqlite3
import datetime
import os
import json
from vpn.server import VPNServer
from vpn.logger import Logger

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'vpn_simulation_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize VPN server and logger
logger = Logger()
vpn_server = VPNServer(logger)

# Ensure database directory exists
os.makedirs('database', exist_ok=True)

# Create database tables if they don't exist
conn = sqlite3.connect('database/vpn_logs.db')
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS connection_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT,
    ip_address TEXT,
    connection_time TIMESTAMP,
    disconnection_time TIMESTAMP NULL,
    status TEXT
)
''')
cursor.execute('''
CREATE TABLE IF NOT EXISTS message_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT,
    ip_address TEXT,
    message TEXT,
    timestamp TIMESTAMP,
    direction TEXT
)
''')
conn.commit()
conn.close()

# Server stats
server_stats = {
    'start_time': datetime.datetime.now(),
    'active_clients': 0,
    'total_messages': 0
}

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/server')
def server():
    uptime = datetime.datetime.now() - server_stats['start_time']
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{hours}h {minutes}m {seconds}s"
    
    return render_template(
        'server.html', 
        active_clients=server_stats['active_clients'],
        total_messages=server_stats['total_messages'],
        uptime=uptime_str
    )

@app.route('/logs')
def logs():
    return render_template('logs.html')

@app.route('/api/logs/connections')
def get_connection_logs():
    date_filter = request.args.get('date', '')
    ip_filter = request.args.get('ip', '')
    
    conn = sqlite3.connect('database/vpn_logs.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = "SELECT * FROM connection_logs WHERE 1=1"
    params = []
    
    if date_filter:
        query += " AND date(connection_time) = ?"
        params.append(date_filter)
    
    if ip_filter:
        query += " AND ip_address LIKE ?"
        params.append(f"%{ip_filter}%")
    
    query += " ORDER BY connection_time DESC"
    
    cursor.execute(query, params)
    logs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(logs)

@app.route('/api/logs/messages')
def get_message_logs():
    date_filter = request.args.get('date', '')
    ip_filter = request.args.get('ip', '')
    content_filter = request.args.get('content', '')
    
    conn = sqlite3.connect('database/vpn_logs.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = "SELECT * FROM message_logs WHERE 1=1"
    params = []
    
    if date_filter:
        query += " AND date(timestamp) = ?"
        params.append(date_filter)
    
    if ip_filter:
        query += " AND ip_address LIKE ?"
        params.append(f"%{ip_filter}%")
    
    if content_filter:
        query += " AND message LIKE ?"
        params.append(f"%{content_filter}%")
    
    query += " ORDER BY timestamp DESC"
    
    cursor.execute(query, params)
    logs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(logs)

@app.route('/api/server/stats')
def get_server_stats():
    uptime = datetime.datetime.now() - server_stats['start_time']
    return jsonify({
        'active_clients': server_stats['active_clients'],
        'total_messages': server_stats['total_messages'],
        'uptime_seconds': uptime.total_seconds()
    })

# Socket events
@socketio.on('connect')
def handle_connect():
    client_id = request.sid
    ip_address = request.remote_addr or '127.0.0.1'
    
    vpn_server.add_client(client_id, ip_address)
    server_stats['active_clients'] += 1
    
    # Log connection
    logger.log_connection(client_id, ip_address)
    
    # Notify client of successful connection
    emit('connection_status', {'status': 'connected', 'client_id': client_id, 'ip': ip_address})
    
    # Broadcast updated stats to all clients
    socketio.emit('server_stats_update', {
        'active_clients': server_stats['active_clients'],
        'total_messages': server_stats['total_messages']
    })

@socketio.on('disconnect')
def handle_disconnect():
    client_id = request.sid
    client = vpn_server.get_client(client_id)
    
    if client:
        # Log disconnection
        logger.log_disconnection(client_id, client['ip_address'])
        
        # Remove client
        vpn_server.remove_client(client_id)
        server_stats['active_clients'] -= 1
        
        # Broadcast updated stats to all clients
        socketio.emit('server_stats_update', {
            'active_clients': server_stats['active_clients'],
            'total_messages': server_stats['total_messages']
        })

@socketio.on('send_message')
def handle_message(data):
    client_id = request.sid
    client = vpn_server.get_client(client_id)
    
    if client and 'message' in data:
        message = data['message']
        
        # Log message
        logger.log_message(client_id, client['ip_address'], message, 'outgoing')
        
        # Process message (simulate VPN server processing)
        response = vpn_server.process_message(client_id, message)
        
        # Log server response
        logger.log_message(client_id, client['ip_address'], response, 'incoming')
        
        # Send response back to client
        emit('receive_message', {
            'message': response,
            'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
        # Update message count
        server_stats['total_messages'] += 2  # One for client message, one for server response
        
        # Broadcast updated stats to all clients
        socketio.emit('server_stats_update', {
            'active_clients': server_stats['active_clients'],
            'total_messages': server_stats['total_messages']
        })
if __name__ == '__main__':
    socketio.run(app, debug=True, host='127.0.0.1', port=5000)

