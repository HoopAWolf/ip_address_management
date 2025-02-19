import pynetbox
from pymongo import MongoClient

# Connect to NetBox API
NETBOX_URL = 'https://demo.netbox.dev/'
NETBOX_API_TOKEN = 'daf5b004cd863cedd7da7d7311fc98ec1638560b'

netbox = pynetbox.api(NETBOX_URL, token=NETBOX_API_TOKEN)

# Connect to MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['ip_address_management']
ip_addresses = db['ip_addresses']
available_addresses = db['available_ip_addresses']
