from .db import ip_addresses

class IPAddress:
    def __init__(self, address, subnet, assigned_to):
        self.address = address
        self.subnet = subnet
        self.assigned_to = assigned_to

    def save(self):
        """Save the IP address to the MongoDB collection."""
        ip_addresses.insert_one({
            'address': self.address,
            'subnet': self.subnet,
            'assigned_to': self.assigned_to
        })

    @staticmethod
    def get_all():
        """Retrieve all IP addresses from the collection."""
        return list(ip_addresses.find())
