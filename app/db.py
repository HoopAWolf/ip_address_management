import pynetbox
from pymongo import MongoClient

# Connect to NetBox API
NETBOX_URL = 'https://netbox.cit.insea.io/'
NETBOX_API_TOKEN = '0095f9fb88dc49741dac2c5717bcf1e6ea887419'

netbox = pynetbox.api(NETBOX_URL, token=NETBOX_API_TOKEN)

# Connect to MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['ip_address_management']
ip_addresses = db['ip_addresses']
available_addresses = db['available_ip_addresses']
