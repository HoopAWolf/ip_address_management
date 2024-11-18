import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QMessageBox, QDialog, QLabel, QLineEdit, QTableWidget, QTableWidgetItem, QTabWidget, QHeaderView, QComboBox
from PyQt5.QtCore import Qt, QThreadPool, QRunnable, pyqtSignal, QObject
from PyQt5.QtGui import QBrush, QColor
from pymongo import MongoClient
import requests
from .ml_models import SubnetPredictionModel
import ipaddress

prefix_list = []

def is_public_ip(ip):
    try:
        ip_obj = ipaddress.ip_address(ip)
        return not ip_obj.is_private  # Returns True if the IP is public
    except ValueError:
        return False  # Invalid IP

class LoginDialog(QDialog):
    """Login Dialog to input base URL and API token."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Login")
        self.setGeometry(150, 150, 300, 150)

        # Labels and inputs
        self.url_label = QLabel("Base URL:")
        self.url_input = QLineEdit()
        self.url_input.setText('https://netbox.cit.insea.io')

        self.token_label = QLabel("API Token:")
        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.Password)

        # Buttons
        self.login_button = QPushButton("Login")
        self.login_button.clicked.connect(self.accept_login)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.url_label)
        layout.addWidget(self.url_input)
        layout.addWidget(self.token_label)
        layout.addWidget(self.token_input)
        layout.addWidget(self.login_button)
        self.setLayout(layout)

        # Variables to hold base URL and token
        self.base_url = None
        self.token = None

    def accept_login(self):
        """Validate and store the input, then accept the dialog."""
        base_url = self.url_input.text().strip()
        token = self.token_input.text().strip()

        if base_url and token:
            self.base_url = base_url
            self.token = token
            self.accept()  # Close dialog
        else:
            QMessageBox.warning(self, "Input Error", "Please provide both Base URL and API Token.")


class AddLocationDialog(QDialog): 
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Location")
        self.setGeometry(150, 150, 300, 200)

        # Create form inputs
        self.location_label = QLabel("Location name:")
        self.location_input = QLineEdit()

        self.add_button = QPushButton("Add Location")
        self.add_button.clicked.connect(self.assign_location)

        # Set layout
        layout = QVBoxLayout()
        layout.addWidget(self.location_label)
        layout.addWidget(self.location_input)
        layout.addWidget(self.add_button)

        self.setLayout(layout)

    def assign_location(self):
        location = self.location_input.text()
        if location:  # Ensure there's text to add
            # Assuming AddIPDialog.groupList is a QComboBox or QListWidget
            self.parent().group_input.addItem(location)  # Add location to groupList in AddIPDialog
            self.close()  # Close dialog after adding

class SubnetDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Find IP Range")
        self.setGeometry(300, 300, 400, 200)
        
        # Create input fields
        self.location_label = QLabel("Enter Location (Country):")
        self.location_input = QLineEdit()
        
        self.host_label = QLabel("Enter Number of Hosts:")
        self.host_input = QLineEdit()
        
        # Button to find available subnet
        self.find_button = QPushButton("Find IP Range")
        self.find_button.clicked.connect(self.find_available_subnet)
        
        # Layout setup
        layout = QVBoxLayout()
        layout.addWidget(self.location_label)
        layout.addWidget(self.location_input)
        layout.addWidget(self.host_label)
        layout.addWidget(self.host_input)
        layout.addWidget(self.find_button)
        self.setLayout(layout)

    def find_available_subnet(self):
        global prefix_list
        country = self.location_input.text()
        
        # Ensure num_hosts is an integer, and handle invalid input
        try:
            num_hosts = int(self.host_input.text())
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter a valid number of hosts.")
            return
        
        # Calculate the required subnet size and prefix length
        required_prefix_length = 32 - (num_hosts + 2).bit_length()
   
        available_subnets = []

        # Iterate through the prefix list to find available prefixes
        for prefix_data in prefix_list:
            if prefix_data['tenant'] == country:  # Filter by country
                # Ensure 'prefix' is a list of valid IP prefixes
                try:
                    network = ipaddress.IPv4Network(prefix_data['prefix'])
                    if network.prefixlen <= required_prefix_length:
                        available_subnets.append({
                            'subnet': network,
                            'tenant': prefix_data['tenant'],
                            'site': prefix_data['site'],
                            'description': prefix_data['description']
                        })
                except ValueError:
                    print(f"Skipping invalid IP prefix: {prefix_data['prefix']}")
        
        # Sort available subnets by size
        available_subnets = sorted(available_subnets, key=lambda x: x['subnet'].prefixlen)

        # Output result
        if available_subnets:
            selected_subnet = available_subnets[0]
            subnet_info = (
                f"Region: {selected_subnet['tenant']}\n"
                f"Location: {selected_subnet['site']}\n"
                f"Description: {selected_subnet['description']}\n"
                f"IP Range: {selected_subnet['subnet']}\n"
                f"Subnet Mask: {selected_subnet['subnet'].netmask}"
            )
            QMessageBox.information(self, "Available Subnet Found", subnet_info)
        else:
            QMessageBox.warning(self, "No Available Subnet", "No suitable subnet available for the given inputs.")

class AddIPDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add IP Address")
        self.setGeometry(150, 150, 300, 200)

        # Initialize the subnet prediction model
        self.subnet_model = SubnetPredictionModel()
        self.subnet_model.train_model()  # Train the model upon initialization

        # Create form inputs
        self.ip_label = QLabel("IP Address:")
        self.ip_input = QLineEdit()

        self.location_name_label = QLabel("Location Name:")
        self.location_name_input = QLineEdit()

        self.num_hosts_label = QLabel("Number of Hosts:")
        self.num_hosts_input = QLineEdit()

        self.group_label = QLabel("Group:")
        self.group_input = QComboBox()
        tempList = ["SG", "VN", "ID", "CN", "MY", "TW", "TH", "VNHCM", "VNHN", "PH", "CNSH", "CNSZ", "CNXM", "CNDG", "CNGZ", "CNYW", "CNNN", "CNHZ", "CNBJ", "DC", "BR", "KR", "USA"]
        tempList.sort()
        self.group_input.addItems(tempList)

        self.add_location_button = QPushButton("Add Country")
        self.add_location_button.clicked.connect(self.open_add_location_dialog)

        self.subnet_label = QLabel("Subnet:")
        self.subnet_output = QLineEdit()

        self.predict_button = QPushButton("Predict Subnet")
        self.predict_button.clicked.connect(self.predict_subnet)

        self.assign_button = QPushButton("Assign IP")
        self.assign_button.clicked.connect(self.assign_ip)

        # Set layout
        layout = QVBoxLayout()
        layout.addWidget(self.ip_label)
        layout.addWidget(self.ip_input)
        layout.addWidget(self.location_name_label)
        layout.addWidget(self.location_name_input)
        layout.addWidget(self.num_hosts_label)
        layout.addWidget(self.num_hosts_input)
        layout.addWidget(self.group_label)
        layout.addWidget(self.group_input)
        layout.addWidget(self.add_location_button)
        layout.addWidget(self.subnet_label)
        layout.addWidget(self.predict_button)
        layout.addWidget(self.subnet_output)
        layout.addWidget(self.assign_button)

        self.setLayout(layout)

    def predict_subnet(self):
        num_hosts = None
        if len(self.num_hosts_input.text()) != 0:
            num_hosts = int(self.num_hosts_input.text())
        else:
            num_hosts = self.subnet_model.calculate_hosts_from_subnet(self.ip_input.text())
            if num_hosts is None:
                num_hosts = 0

        group = self.group_input.currentText()  # Get the group from the input

        # First, try to predict using the machine learning model
        try:
            predicted_subnet = self.subnet_model.predict_subnet(num_hosts, group)  # Pass both num_hosts and group
            self.subnet_output.setText(f"{predicted_subnet}")
        except Exception as e:
            print(f"ML Model prediction failed: {e}")
            # Fallback to basic logic if ML model fails
            predicted_subnet = self.subnet_model_predict(num_hosts)  # Adjust if you need a group fallback
            self.subnet_output.setText(f"{predicted_subnet}")

    def open_add_location_dialog(self):
        dialog = AddLocationDialog(self)
        dialog.exec_()

    def subnet_model_predict(self, num_hosts):
        """Fallback logic for predicting subnet size based on number of hosts."""
        if num_hosts <= 14:
            return "/28"  # Suitable for 14 hosts
        elif num_hosts <= 62:
            return "/26"  # Suitable for 62 hosts
        elif num_hosts <= 254:
            return "/24"  # Suitable for 254 hosts
        else:
            return "/16"  # Default to /16 for larger host requirements

    def is_subnet_available(self, subnet):
        try:
            # Connect to MongoDB
            client = MongoClient('mongodb://localhost:27017/')
            db = client['ip_address_management']
            collection = db['ip_addresses']

            # Fetch all IP addresses and subnets from the database
            ip_addresses = list(collection.find({}, {'name': 1, 'address': 1, 'subnet': 1, '_id': 0}))

            # Check if the requested subnet overlaps with any existing subnet
            requested_network = ipaddress.ip_network(subnet, strict=False)

            for ip_data in ip_addresses:
                existing_subnet = ip_data.get('address') + ip_data.get('subnet')
                
                if existing_subnet:
                    existing_network = ipaddress.ip_network(existing_subnet, strict=False)
                    if requested_network.overlaps(existing_network):
                        QMessageBox.warning(self, "Subnet Unavailable", f"The subnet {subnet} is already in use.")
                        return False  # Subnet is already in use

            return True  # Subnet is available
        except Exception as e:
            print(f"Failed to check subnet availability: {e}")
            QMessageBox.warning(self, "Failed to check subnet", f"{e}")
            return False

    def assign_ip(self):
        ip_address = self.ip_input.text()
        location_name = self.location_name_input.text()
        subnet = self.subnet_output.text().replace("Predicted Subnet: ", "")

        if is_public_ip(ip_address):
            reply = QMessageBox.warning(self, "Public IP Warning", 
                                        "The provided IP address is a public IP. Do you want to proceed?", 
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                return  # Don't proceed if the user selects 'No'
            
        if not self.is_subnet_available(ip_address + subnet):
            return  # Stop the process if the subnet is already in use

        if ip_address and subnet:
            try:
                client = MongoClient('mongodb://localhost:27017/')
                db = client['ip_address_management']
                collection = db['ip_addresses']
                group = self.group_input.currentText()

                # Add group to MongoDB document
                collection.insert_one({
                    'name': location_name,
                    'address': ip_address,
                    'subnet': subnet,
                    'group': group  # Store group type in MongoDB
                })

                # Clear input fields
                self.ip_input.clear()
                self.num_hosts_input.clear()
                self.subnet_output.setText("---")

                QMessageBox.information(self, "Success", "IP Address assigned successfully!")
                self.accept()  # Close the dialog on success
            except Exception as e:
                QMessageBox.critical(self, "Database Error", f"Failed to assign IP address: {e}")
        else:
            QMessageBox.warning(self, "Input Error", "Please fill out all fields.")

class WorkerSignals(QObject):
    """Defines the signals available from a running worker thread."""
    success = pyqtSignal(list)   # Emitted when VLANs are successfully imported
    error = pyqtSignal(str)      # Emitted when an error occurs


class ImportVLANWorker(QRunnable):
    """Worker thread for importing VLANs in the background."""
    def __init__(self, base_url, headers, search_input):
        super().__init__()
        self.base_url = base_url
        self.headers = headers
        self.search_input = search_input
        self.signals = WorkerSignals()


    def run(self):
        """Run the importing process in a separate thread."""
        try:
            vlan_url = f'{self.base_url}/api/ipam/vlans/?limit=5000'
            vlan_response = requests.get(vlan_url, headers=self.headers, verify=False)
            vlan_response.raise_for_status()
            vlans = vlan_response.json().get('results', [])

            filtered_vlans = []
            for vlan in vlans:
                vlan_id = vlan['id']
                vlan_name = vlan['name']
                vlan_site = vlan['site']['display'] if vlan.get('site') else 'No site'
                vlan_tenant = vlan['tenant']['display'] if vlan.get('tenant') else 'No tenant'
                vlan_status = vlan['status']['label'] if 'status' in vlan else 'Unknown'
                vlan_description = vlan.get('description', 'No description')

                if self.search_input not in vlan_name:
                    continue

                # Fetch prefixes for this VLAN
                prefixes_url = f'{self.base_url}/api/ipam/prefixes/?vlan_id={vlan_id}'
                prefix_response = requests.get(prefixes_url, headers=self.headers, verify=False)
                prefix_response.raise_for_status()
                prefixes = [prefix['prefix'] for prefix in prefix_response.json().get('results', [])]

                filtered_vlans.append({
                    'name': vlan_name,
                    'site': vlan_site,
                    'tenant': vlan_tenant,
                    'prefixes': prefixes,
                    'status': vlan_status,
                    'description': vlan_description
                })

            self.signals.success.emit(filtered_vlans)

        except Exception as e:
            self.signals.error.emit(str(e))

class ImportPrefixWorker(QRunnable):
    """Worker thread for importing prefixes in the background."""
    
    def __init__(self, base_url, headers, search_input):
        super().__init__()
        self.base_url = base_url
        self.headers = headers
        self.search_input = search_input
        self.signals = WorkerSignals()

    def run(self):
        global prefix_list
        try:
            # Define the URL for fetching prefixes
            prefix_url = f'{self.base_url}/api/ipam/prefixes/?limit=5000'
            prefix_response = requests.get(prefix_url, headers=self.headers, verify=False)
            prefix_response.raise_for_status()
            prefixes_data = prefix_response.json().get('results', [])

            filtered_prefixes = []
            for prefix in prefixes_data:
                prefix_address = prefix['prefix']
                prefix_site = prefix['site']['display'] if prefix.get('site') else 'No site'
                prefix_tenant = prefix['tenant']['display'] if prefix.get('tenant') else 'No tenant'
                prefix_status = prefix['status']['label'] if 'status' in prefix else 'Unknown'
                prefix_description = prefix.get('description', 'No description')

                if self.search_input and self.search_input not in prefix_address:
                    continue

                # Get available IPs within each prefix
                available_ips = self.get_available_ips(prefix_address)

                # Append each prefix entry with relevant information
                filtered_prefixes.append({
                    'prefix': prefix_address,
                    'site': prefix_site,
                    'tenant': prefix_tenant,
                    'status': prefix_status,
                    'description': prefix_description,
                    'available_ips': available_ips
                })

            prefix_list = filtered_prefixes
            # Emit filtered prefixes list
            self.signals.success.emit(filtered_prefixes)

        except Exception as e:
            self.signals.error.emit(str(e))

    def get_available_ips(self, prefix_address):
        """Retrieve available IPs within the given prefix range."""
        available_ips = []
        try:
            # Define the URL for fetching IP addresses in the prefix range
            ip_url = f"{self.base_url}/api/ipam/ip-addresses/?parent={prefix_address}"
            response = requests.get(ip_url, headers=self.headers, verify=False)
            response.raise_for_status()
            
            # Fetch all used IP addresses
            used_ips = [ip['address'].split('/')[0] for ip in response.json().get('results', [])]
            used_ips = sorted(ipaddress.IPv4Address(ip) for ip in used_ips)  # Sort IPs for easier gap calculation
            
            # Calculate available IPs by finding gaps between used IPs
            network = ipaddress.IPv4Network(prefix_address)
            all_ips = list(network.hosts())  # Generate all usable IPs in the subnet

            # Identify available IPs by excluding used ones
            available_ips = [str(ip) for ip in all_ips if ip not in used_ips]

        except Exception as e:
            print(f"Error fetching IPs for prefix {prefix_address}: {str(e)}")
        
        return available_ips


class IPAddressManager(QMainWindow):
    def __init__(self, base_url, api_token):
        super().__init__()
        self.base_url = base_url
        self.api_token = api_token
        self.setWindowTitle("IP Address Management")
        self.setGeometry(100, 100, 600, 400)

         # Initialize thread pool
        self.thread_pool = QThreadPool()

        # Create main layout
        self.main_layout = QVBoxLayout()

        # Create tab widget
        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)

        # Create first tab (for IP addresses)
        self.ip_tab = QWidget()
        self.tab_widget.addTab(self.ip_tab, "IP Addresses")
        self.setup_ip_tab()

        # Create second tab (for VLANs)
        self.vlan_tab = QWidget()
        self.tab_widget.addTab(self.vlan_tab, "VLANs")
        self.setup_vlan_tab()

        # Create second tab (for Prefixes)
        self.prefix_tab = QWidget()
        self.tab_widget.addTab(self.prefix_tab, "Prefixes")
        self.setup_prefix_tab()

        # Set main layout
        container = QWidget()
        container.setLayout(self.main_layout)
        self.setCentralWidget(container)

    def setup_ip_tab(self):
        layout = QVBoxLayout()

        self.search_address_label = QLabel("Search IP Address")
        self.search_address_input = QLineEdit()

         # Create Widgets
        self.ip_table = QTableWidget()
        self.ip_table.setColumnCount(3)
        self.ip_table.setHorizontalHeaderLabels(["Name", "IP Address", "Subnet"])
        self.ip_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.update_button = QPushButton("Update List")
        self.update_button.clicked.connect(self.update_ip_list)

        self.add_button = QPushButton("Add IP Address")
        self.add_button.clicked.connect(self.show_add_ip_dialog)

        self.find_avaialbe_ip_button = QPushButton("Find Available IP Addresses")
        self.find_avaialbe_ip_button.clicked.connect(self.find_available_ip_address)

        # Set Layout
        layout = QVBoxLayout()
        layout.addWidget(self.search_address_label)
        layout.addWidget(self.search_address_input)
        layout.addWidget(self.ip_table)
        layout.addWidget(self.update_button)
        layout.addWidget(self.add_button)
        layout.addWidget(self.find_avaialbe_ip_button)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.ip_tab.setLayout(layout)

    def setup_vlan_tab(self):
        layout = QVBoxLayout()

        # Add button to import VLANs
        self.search_label = QLabel("Search by name:")
        self.search_input = QLineEdit()
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.start_import)
        self.import_vlan_button = QPushButton("Import VLANs")
        self.import_vlan_button.clicked.connect(self.start_import)

        # Initialize the 'Loading...' label
        self.loading_label = QLabel("Loading...", self)
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setVisible(False)  # Hide initially

        layout.addWidget(self.import_vlan_button)
        layout.addWidget(self.search_label)
        layout.addWidget(self.search_input)
        layout.addWidget(self.search_button)
        layout.addWidget(self.loading_label)

        # Create a table to display VLANs and prefixes
        self.vlan_table = QTableWidget()
        self.vlan_table.setColumnCount(5)
        self.vlan_table.setHorizontalHeaderLabels(["VLAN Name", "Site", "Tenant", "Prefixes", "Status", "Description"])
        layout.addWidget(self.vlan_table)

        self.vlan_tab.setLayout(layout)

    def start_loading(self):
        """Show the loading message when a task starts."""
        self.loading_label.setVisible(True)  # Show 'Loading...' message

    def stop_loading(self):
        """Hide the loading message when the task completes."""
        self.loading_label.setVisible(False)  # Hide 'Loading...' message

    def start_import(self):
        self.start_loading()
        """Start the VLAN importing process in a separate thread."""
        headers = {
            'Authorization': 'Token ' + self.api_token,  # Replace with your API token
        }

        search_term = self.search_input.text()

        # Create a worker for importing VLANs
        worker = ImportVLANWorker(self.base_url, headers, search_term)
        worker.signals.success.connect(self.update_table)
        worker.signals.error.connect(self.show_error)

        # Execute the worker in a separate thread
        self.thread_pool.start(worker)

    def start_prefix_loading(self):
        """Show the loading message when a task starts."""
        self.prefix_loading_label.setVisible(True)  # Show 'Loading...' message

    def stop_prefix_loading(self):
        """Hide the loading message when the task completes."""
        self.prefix_loading_label.setVisible(False)  # Hide 'Loading...' message

    def start_prefix_import(self):
        self.start_prefix_loading()
        """Start the VLAN importing process in a separate thread."""
        headers = {
            'Authorization': 'Token ' + self.api_token,  # Replace with your API token
        }

        search_term = self.search_input.text()

        # Create a worker for importing VLANs
        worker = ImportPrefixWorker(self.base_url, headers, search_term)
        worker.signals.success.connect(self.update_prefix_table)
        worker.signals.error.connect(self.show_error)

        # Execute the worker in a separate thread
        self.thread_pool.start(worker)

    def update_table(self, vlans):
        """Update the table with imported VLANs."""
        self.vlan_table.setRowCount(0)  # Clear current table

        for vlan in vlans:

            row_position = self.vlan_table.rowCount()
            self.vlan_table.insertRow(row_position)

            # Add data to table cells
            self.vlan_table.setItem(row_position, 0, QTableWidgetItem(vlan['name']))
            self.vlan_table.setItem(row_position, 1, QTableWidgetItem(vlan['site']))  # Site column
            self.vlan_table.setItem(row_position, 2, QTableWidgetItem(vlan['tenant']))  # Tenant column
            self.vlan_table.setItem(row_position, 3, QTableWidgetItem(", ".join(vlan['prefixes'])))
            self.vlan_table.setItem(row_position, 4, QTableWidgetItem(vlan['status']))
            self.vlan_table.setItem(row_position, 5, QTableWidgetItem(vlan['description']))

        self.stop_loading()

    def update_prefix_table(self, prefixes):
        """Update the table with imported prefixes."""
        self.prefix_table.setRowCount(0)  # Clear the current table

        for prefix in prefixes:
            row_position = self.prefix_table.rowCount()
            self.prefix_table.insertRow(row_position)

            # Add data to table cells
            self.prefix_table.setItem(row_position, 0, QTableWidgetItem(prefix['prefix']))      # Prefix column

             # Set RGBA font color
            custom_color = QColor(72, 126, 176, 255)  # (R, G, B, A) - Full opacity
            site_item = QTableWidgetItem(prefix['site'])
            site_item.setForeground(QBrush(custom_color))
            self.prefix_table.setItem(row_position, 1, site_item)        # Site column

             # Set RGBA font color
            custom_color = QColor(234, 144, 61, 255)  # (R, G, B, A) - Full opacity
            tenant_item = QTableWidgetItem(prefix['tenant'])
            tenant_item.setForeground(QBrush(custom_color))
            self.prefix_table.setItem(row_position, 2, tenant_item)      # Tenant column

             # Set RGBA font color
            custom_color = QColor(85, 170, 85, 255)  # (R, G, B, A) - Full opacity
            status_item = QTableWidgetItem(prefix['status'])
            status_item.setForeground(QBrush(custom_color))
            self.prefix_table.setItem(row_position, 3, status_item)      # Status column

            # Limit the displayed IPs to 20 and indicate more if available
            available_ips = prefix.get('available_ips', [])
            if len(available_ips) > 5:
                displayed_ips = [f"{len(available_ips)} available"]
            else:
                displayed_ips = available_ips

            # Format the IPs for multi-line display
            ip_text = ", ".join(displayed_ips)
            ip_item = QTableWidgetItem(ip_text)

            # Set RGBA font color
            custom_color = QColor(0, 242, 212, 255)  # (R, G, B, A) - Full opacity
            ip_item.setForeground(QBrush(custom_color))

            ip_item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop)  # Align text to the top-left for readability
            self.prefix_table.setItem(row_position, 4, ip_item)  # Available IPs column



        self.populate_filter_combos()
        self.stop_prefix_loading()

    def populate_filter_combos(self):
        """Populate country and site combo boxes with unique values."""
        global prefix_list

        # Extract unique countries and sites from prefix_list
        countries = sorted({prefix['tenant'] for prefix in prefix_list if prefix['tenant']})
        sites = sorted({prefix['site'] for prefix in prefix_list if prefix['site']})

        # Update country combo
        self.country_combo.clear()
        self.country_combo.addItem("All")  # Default option for no filter
        self.country_combo.addItems(countries)

        # Update site combo
        self.site_combo.clear()
        self.site_combo.addItem("All")    # Default option for no filter
        self.site_combo.addItems(sites)

    def show_error(self, error_message):
        """Display an error message if the import fails."""
        QMessageBox.critical(self, "Import Error", f"Failed to import prefixes: {error_message}")



    def update_ip_list(self):
        self.ip_table.setRowCount(0)  # Clear the current table

        try:
            client = MongoClient('mongodb://localhost:27017/')
            db = client['ip_address_management']
            collection = db['ip_addresses']

            # Fetch IP addresses, group them by 'group'
            ip_addresses = list(collection.find({}, {'name': 1, 'address': 1, 'subnet': 1, 'group': 1, '_id': 0}))
            ip_addresses.sort(key=lambda x: x['group'])  # Sort by group

            current_group = None
            row_position = 0

            # Check if list is empty
            if len(ip_addresses) == 0:
                self.ip_table.setRowCount(1)
                self.ip_table.setItem(0, 0, QTableWidgetItem("Nothing in database"))
                self.ip_table.setSpan(0, 0, 1, 3)
            else:
                for ip in ip_addresses:
                    group = ip.get('group', 'No Group')

                    if self.search_address_input.text() not in ip.get('address', 'No Address Found'):
                        continue

                    # Add group header row
                    if group != current_group:
                        current_group = group
                        self.ip_table.insertRow(row_position)
                        group_item = QTableWidgetItem(f"Group: {current_group}")
                        group_item.setBackground(Qt.darkGray)  # Set group header background color
                        self.ip_table.setItem(row_position, 0, group_item)
                        self.ip_table.setSpan(row_position, 0, 1, 3)  # Span across all columns
                        row_position += 1

                    # Add IP address details row
                    self.ip_table.insertRow(row_position)
                    self.ip_table.setItem(row_position, 0, QTableWidgetItem(ip.get('name', 'No Name Found')))
                    self.ip_table.setItem(row_position, 1, QTableWidgetItem(ip.get('address', 'No Address Found')))
                    self.ip_table.setItem(row_position, 2, QTableWidgetItem(ip.get('subnet', 'No Subnet')))
                    row_position += 1

        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to fetch IP addresses: {e}")

    def setup_prefix_tab(self):
        layout = QVBoxLayout()

        # Add button to import VLANs
        self.search_label = QLabel("Search by IP:")
        self.search_input = QLineEdit()
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.start_prefix_import)
        self.import_prefix_button = QPushButton("Import Prefixes")
        self.import_prefix_button.clicked.connect(self.start_prefix_import)
        self.country_label = QLabel("Filter by Country:")
        self.country_combo = QComboBox()
        self.country_combo.setEditable(False)  # Prevent manual editing
        self.country_combo.addItem("All")      # Default option for no filter

        self.site_label = QLabel("Filter by Site:")
        self.site_combo = QComboBox()
        self.site_combo.setEditable(False)     # Prevent manual editing
        self.site_combo.addItem("All")         # Default option for no filter

        self.filter_button = QPushButton("Apply Filters")
        self.filter_button.clicked.connect(self.apply_filters)

        # Initialize the 'Loading...' label
        self.prefix_loading_label = QLabel("Loading...", self)
        self.prefix_loading_label.setAlignment(Qt.AlignCenter)
        self.prefix_loading_label.setVisible(False)  # Hide initially



        layout.addWidget(self.import_prefix_button)
        layout.addWidget(self.search_label)
        layout.addWidget(self.search_input)
        layout.addWidget(self.search_button)
        layout.addWidget(self.country_label)
        layout.addWidget(self.country_combo)
        layout.addWidget(self.site_label)
        layout.addWidget(self.site_combo)
        layout.addWidget(self.filter_button)
        layout.addWidget(self.prefix_loading_label)

        # Create a table to display VLANs and prefixes
        self.prefix_table = QTableWidget()
        self.prefix_table.setColumnCount(5)
        self.prefix_table.setHorizontalHeaderLabels(["Prefix", "Site", "Tenant", "Status", "Availble Addresses"])
        layout.addWidget(self.prefix_table)

        self.prefix_tab.setLayout(layout)

    def apply_filters(self):
        """Filter prefixes based on selected country and site."""
        selected_country = self.country_combo.currentText()
        selected_site = self.site_combo.currentText()

        # Filter the prefix list
        filtered_prefixes = [
            prefix for prefix in prefix_list
            if (selected_country == "All" or prefix['tenant'] == selected_country) and
            (selected_site == "All" or prefix['site'] == selected_site)
        ]

        # Update the table with the filtered data
        self.update_prefix_table(filtered_prefixes)

    def find_available_ip_address(self):
        dialog = SubnetDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            return

    def show_add_ip_dialog(self):
        dialog = AddIPDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.update_ip_list()  # Update the list if a new IP is added


def main():
    app = QApplication(sys.argv)
    login_dialog = LoginDialog()
    if login_dialog.exec_() == QDialog.Accepted:
        # Open main window after login
        window = IPAddressManager(login_dialog.base_url, login_dialog.token)
        window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
