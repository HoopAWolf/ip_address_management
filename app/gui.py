import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QMessageBox, QDialog, QLabel, QLineEdit, QTableWidget, QTableWidgetItem, QTabWidget, QHeaderView, QComboBox
from PyQt5.QtCore import Qt, QThreadPool, QRunnable, pyqtSignal, QObject
from pymongo import MongoClient
import requests
from .ml_models import SubnetPredictionModel

class LoginDialog(QDialog):
    """Login Dialog to input base URL and API token."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Login")
        self.setGeometry(150, 150, 300, 150)

        # Labels and inputs
        self.url_label = QLabel("Base URL:")
        self.url_input = QLineEdit()
        self.url_input.setText('https://demo.netbox.dev')

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

        self.num_hosts_label = QLabel("Number of Hosts:")
        self.num_hosts_input = QLineEdit()

        self.group_label = QLabel("Group:")
        self.group_input = QComboBox()
        self.group_input.addItems(["Office IPs", "IDC IPs", "Warehouse IPs"])

        self.subnet_label = QLabel("Predicted Subnet Size:")
        self.subnet_output = QLabel("---")

        self.predict_button = QPushButton("Predict Subnet")
        self.predict_button.clicked.connect(self.predict_subnet)

        self.assign_button = QPushButton("Assign IP")
        self.assign_button.clicked.connect(self.assign_ip)

        # Set layout
        layout = QVBoxLayout()
        layout.addWidget(self.ip_label)
        layout.addWidget(self.ip_input)
        layout.addWidget(self.num_hosts_label)
        layout.addWidget(self.num_hosts_input)
        layout.addWidget(self.group_label)
        layout.addWidget(self.group_input)
        layout.addWidget(self.predict_button)
        layout.addWidget(self.subnet_label)
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
            self.subnet_output.setText(f"Predicted Subnet: {predicted_subnet}")
        except Exception as e:
            print(f"ML Model prediction failed: {e}")
            # Fallback to basic logic if ML model fails
            predicted_subnet = self.subnet_model_predict(num_hosts)  # Adjust if you need a group fallback
            self.subnet_output.setText(f"Predicted Subnet: {predicted_subnet}")




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


    def assign_ip(self):
        ip_address = self.ip_input.text()
        subnet = self.subnet_output.text().replace("Predicted Subnet: ", "")

        if ip_address and subnet:
            try:
                client = MongoClient('mongodb://localhost:27017/')
                db = client['ip_address_management']
                collection = db['ip_addresses']
                group = self.group_input.currentText()

                # Add group to MongoDB document
                collection.insert_one({
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

        # Set main layout
        container = QWidget()
        container.setLayout(self.main_layout)
        self.setCentralWidget(container)

    def setup_ip_tab(self):
        layout = QVBoxLayout()

         # Create Widgets
        self.ip_table = QTableWidget()
        self.ip_table.setColumnCount(2)
        self.ip_table.setHorizontalHeaderLabels(["IP Address", "Subnet"])
        self.ip_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.update_button = QPushButton("Update List")
        self.update_button.clicked.connect(self.update_ip_list)

        self.add_button = QPushButton("Add IP Address")
        self.add_button.clicked.connect(self.show_add_ip_dialog)

        # Set Layout
        layout = QVBoxLayout()
        layout.addWidget(self.ip_table)
        layout.addWidget(self.update_button)
        layout.addWidget(self.add_button)

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

    def show_error(self, error_message):
        """Display an error message if the import fails."""
        QMessageBox.critical(self, "Import Error", f"Failed to import VLANs: {error_message}")




    def update_ip_list(self):
        self.ip_table.setRowCount(0)  # Clear the current table

        try:
            client = MongoClient('mongodb://localhost:27017/')
            db = client['ip_address_management']
            collection = db['ip_addresses']

            # Fetch IP addresses, group them by 'group'
            ip_addresses = list(collection.find({}, {'address': 1, 'subnet': 1, 'group': 1, '_id': 0}))
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
                    self.ip_table.setItem(row_position, 0, QTableWidgetItem(ip.get('address', 'No Address Found')))
                    self.ip_table.setItem(row_position, 1, QTableWidgetItem(ip.get('subnet', 'No Subnet')))
                    row_position += 1

        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to fetch IP addresses: {e}")


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
