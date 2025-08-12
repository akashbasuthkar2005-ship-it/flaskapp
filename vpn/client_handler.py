import datetime
import socket
import threading
import time
import random

class VPNClient:
    def __init__(self, client_id, ip_address, server):
        self.client_id = client_id
        self.ip_address = ip_address
        self.server = server
        self.connected = False
        self.connection_time = None
        self.disconnection_time = None
        self.messages = []
    
    def connect(self):
        """Simulate connecting to the VPN server"""
        if not self.connected:
            self.connected = True
            self.connection_time = datetime.datetime.now()
            return True
        return False
    
    def disconnect(self):
        """Simulate disconnecting from the VPN server"""
        if self.connected:
            self.connected = False
            self.disconnection_time = datetime.datetime.now()
            return True
        return False
    
    def send_message(self, message):
        """Send a message to the VPN server"""
        if self.connected:
            self.messages.append({
                'content': message,
                'timestamp': datetime.datetime.now(),
                'direction': 'outgoing'
            })
            # Simulate network delay
            time.sleep(random.uniform(0.05, 0.2))
            return True
        return False
    
    def receive_message(self, message):
        """Receive a message from the VPN server"""
        if self.connected:
            self.messages.append({
                'content': message,
                'timestamp': datetime.datetime.now(),
                'direction': 'incoming'
            })
            return True
        return False

class ClientHandler:
    def __init__(self, server):
        self.server = server
        self.clients = {}
        self.next_client_id = 1
    
    def create_client(self, ip_address=None):
        """Create a new VPN client"""
        if ip_address is None:
            # Generate a random IP if none provided
            ip_parts = [str(random.randint(1, 254)) for _ in range(4)]
            ip_address = '.'.join(ip_parts)
        
        client_id = f"client_{self.next_client_id}"
        self.next_client_id += 1
        
        client = VPNClient(client_id, ip_address, self.server)
        self.clients[client_id] = client
        
        return client
    
    def remove_client(self, client_id):
        """Remove a client"""
        if client_id in self.clients:
            client = self.clients[client_id]
            client.disconnect()
            del self.clients[client_id]
            return True
        return False
    
    def get_client(self, client_id):
        """Get a client by ID"""
        return self.clients.get(client_id)
    
    def get_active_clients(self):
        """Get all active clients"""
        return [client for client in self.clients.values() if client.connected]
