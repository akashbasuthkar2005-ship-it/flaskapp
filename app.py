

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_socketio import SocketIO, emit, disconnect
import sqlite3
import datetime
import os
import json
from functools import wraps
from vpn.server import VPNServer
from vpn.logger import Logger

# Initialize Flask app
from datetime import timedelta
app = Flask(__name__)

app.config['SECRET_KEY'] = 'vpn_simulation_secret_key'
# Session lifetime: 1 day
app.permanent_session_lifetime = timedelta(days=1)
socketio = SocketIO(app, cors_allowed_origins="*")
 
# Logout route (must be after app is defined)
@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have been logged out.')
    return redirect(url_for('login'))

# User data file
USER_DATA_FILE = 'database/users.json'

# Ensure database directory exists
os.makedirs('database', exist_ok=True)

# Ensure user data file exists
if not os.path.exists(USER_DATA_FILE):
    with open(USER_DATA_FILE, 'w') as f:
        json.dump({}, f)

# Initialize VPN server and logger
logger = Logger()
vpn_server = VPNServer(logger)

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
# --- NEW: nodes table for "everyone is a server+client" presence tracking ---
cursor.execute('''
CREATE TABLE IF NOT EXISTS nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    username TEXT,
    ip TEXT,
    user_agent TEXT,
    is_server INTEGER DEFAULT 1,
    is_client INTEGER DEFAULT 1,
    last_seen TIMESTAMP
)
''')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_nodes_last_seen ON nodes(last_seen)')
conn.commit()
conn.close()

# Server stats
server_stats = {
    'start_time': datetime.datetime.now(),
    'active_clients': 0,
    'total_messages': 0
}

# Helpers for nodes presence
def _node_db():
    return sqlite3.connect('database/vpn_logs.db')

def _now():
    return datetime.datetime.utcnow()

# Routes

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# Root: redirect to /index if logged in, else to /login
@app.route('/', methods=['GET'])
def root():
    if 'username' in session:
        return redirect(url_for('index'))
    return redirect(url_for('login'))

# Login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        with open(USER_DATA_FILE, 'r') as f:
            users = json.load(f)
        if username in users and users[username] == password:
            session.permanent = True
            session['username'] = username
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')

# Signup page
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        with open(USER_DATA_FILE, 'r') as f:
            users = json.load(f)
        if username in users:
            flash('Username already exists')
        else:
            users[username] = password
            with open(USER_DATA_FILE, 'w') as f2:
                json.dump(users, f2)
            flash('Account created! Please log in.')
            return redirect(url_for('login'))
    return render_template('signup.html')

# Main page (requires login)
@app.route('/index')
@login_required
def index():
    return render_template('index.html')


@app.route('/server')
@login_required
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
@login_required
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

# --- NEW: Everyone who opens the site becomes an active node (server+client) ---

@app.route('/api/nodes/register', methods=['POST'])
def nodes_register():
    # Use login username if available; else treat as guest
    sid = session.get('username') or request.cookies.get('session') or request.remote_addr
    conn = _node_db()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO nodes (session_id, username, ip, user_agent, is_server, is_client, last_seen)
        VALUES (?, ?, ?, ?, 1, 1, ?)
    ''', (
        sid,
        session.get('username'),
        request.headers.get('X-Forwarded-For', request.remote_addr),
        request.headers.get('User-Agent', ''),
        _now()
    ))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/nodes/heartbeat', methods=['POST'])
def nodes_heartbeat():
    sid = session.get('username') or request.cookies.get('session') or request.remote_addr
    conn = _node_db()
    cur = conn.cursor()
    cur.execute('UPDATE nodes SET last_seen=? WHERE session_id=?', (_now(), sid))
    if cur.rowcount == 0:
        cur.execute('''
            INSERT INTO nodes (session_id, username, ip, user_agent, is_server, is_client, last_seen)
            VALUES (?, ?, ?, ?, 1, 1, ?)
        ''', (
            sid,
            session.get('username'),
            request.headers.get('X-Forwarded-For', request.remote_addr),
            request.headers.get('User-Agent', ''),
            _now()
        ))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/nodes/active')
def nodes_active():
    cutoff = _now() - datetime.timedelta(seconds=60)
    conn = _node_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute('SELECT username, ip, user_agent, last_seen FROM nodes WHERE last_seen >= ? ORDER BY last_seen DESC', (cutoff,))
    rows = []
    for r in cur.fetchall():
        rows.append({
            'username': r['username'],
            'ip': r['ip'],
            'user_agent': r['user_agent'],
            'last_seen': r['last_seen']  # stored as timestamp; fine for JSON if string; else cast below
        })
    conn.close()
    # ensure JSON-safe timestamp string
    for r in rows:
        if isinstance(r['last_seen'], (datetime.datetime, )):
            r['last_seen'] = r['last_seen'].isoformat()
    return jsonify({'active': rows, 'count': len(rows)})

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
    socketio.run(app, debug=True, host='127.0.0.1', port=5001)
