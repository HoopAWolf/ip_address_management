import pynetbox
from pymongo import MongoClient

# Connect to NetBox API
NETBOX_URL = 'https://netbox.cit.insea.io'
NETBOX_API_TOKEN = 'e3d318664caba8355bcea30a00237ae38c02b357'

netbox = pynetbox.api(NETBOX_URL, token=NETBOX_API_TOKEN)

# Connect to MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['ip_address_management']
