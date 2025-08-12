import datetime
import random
import time

class VPNServer:
    def __init__(self, logger):
        self.clients = {}
        self.logger = logger
    
    def add_client(self, client_id, ip_address):
        """Add a new client to the VPN server"""
        self.clients[client_id] = {
            'ip_address': ip_address,
            'connection_time': datetime.datetime.now(),
            'messages': []
        }
        return True
    
    def remove_client(self, client_id):
        """Remove a client from the VPN server"""
        if client_id in self.clients:
            del self.clients[client_id]
            return True
        return False
    
    def get_client(self, client_id):
        """Get client information"""
        return self.clients.get(client_id)
    
    def get_active_clients_count(self):
        """Get the number of active clients"""
        return len(self.clients)
    
    def process_message(self, client_id, message):
        """Process a message from a client and return a response"""
        # Simulate processing delay
        time.sleep(random.uniform(0.1, 0.5))
        
        # Store message in client history
        if client_id in self.clients:
            self.clients[client_id]['messages'].append({
                'content': message,
                'timestamp': datetime.datetime.now()
            })
        
        # Generate response based on message content
        if "ping" in message.lower():
            return f"PONG! Server received your ping at {datetime.datetime.now().strftime('%H:%M:%S')}"
        elif "status" in message.lower():
            return f"VPN Server Status: ONLINE | Active Clients: {self.get_active_clients_count()}"
        elif "help" in message.lower():
            return "Available commands: ping, status, help, disconnect"
        elif "disconnect" in message.lower():
            return "Preparing to disconnect. Please confirm by closing the connection."
        else:
            return f"Message received and encrypted. Length: {len(message)} characters."
