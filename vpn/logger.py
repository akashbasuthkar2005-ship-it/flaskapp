import sqlite3
import datetime

class Logger:
    def __init__(self, db_path='database/vpn_logs.db'):
        self.db_path = db_path
    
    def _get_connection(self):
        """Get a database connection"""
        conn = sqlite3.connect(self.db_path)
        return conn
    
    def log_connection(self, client_id, ip_address):
        """Log a client connection"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO connection_logs (client_id, ip_address, connection_time, status) VALUES (?, ?, ?, ?)",
            (client_id, ip_address, datetime.datetime.now(), 'connected')
        )
        
        conn.commit()
        conn.close()
    
    def log_disconnection(self, client_id, ip_address):
        """Log a client disconnection"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Update the connection log with disconnection time
        cursor.execute(
            "UPDATE connection_logs SET disconnection_time = ?, status = ? WHERE client_id = ? AND status = 'connected'",
            (datetime.datetime.now(), 'disconnected', client_id)
        )
        
        conn.commit()
        conn.close()
    
    def log_message(self, client_id, ip_address, message, direction):
        """Log a message (outgoing from client or incoming from server)"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO message_logs (client_id, ip_address, message, timestamp, direction) VALUES (?, ?, ?, ?, ?)",
            (client_id, ip_address, message, datetime.datetime.now(), direction)
        )
        
        conn.commit()
        conn.close()
    
    def get_connection_logs(self, filters=None):
        """Get connection logs with optional filters"""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM connection_logs"
        params = []
        
        if filters:
            conditions = []
            if 'client_id' in filters:
                conditions.append("client_id = ?")
                params.append(filters['client_id'])
            if 'ip_address' in filters:
                conditions.append("ip_address LIKE ?")
                params.append(f"%{filters['ip_address']}%")
            if 'date' in filters:
                conditions.append("date(connection_time) = ?")
                params.append(filters['date'])
            if 'status' in filters:
                conditions.append("status = ?")
                params.append(filters['status'])
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY connection_time DESC"
        
        cursor.execute(query, params)
        logs = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return logs
    
    def get_message_logs(self, filters=None):
        """Get message logs with optional filters"""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM message_logs"
        params = []
        
        if filters:
            conditions = []
            if 'client_id' in filters:
                conditions.append("client_id = ?")
                params.append(filters['client_id'])
            if 'ip_address' in filters:
                conditions.append("ip_address LIKE ?")
                params.append(f"%{filters['ip_address']}%")
            if 'date' in filters:
                conditions.append("date(timestamp) = ?")
                params.append(filters['date'])
            if 'message' in filters:
                conditions.append("message LIKE ?")
                params.append(f"%{filters['message']}%")
            if 'direction' in filters:
                conditions.append("direction = ?")
                params.append(filters['direction'])
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY timestamp DESC"
        
        cursor.execute(query, params)
        logs = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return logs
