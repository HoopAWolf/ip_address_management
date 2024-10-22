import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QMessageBox, QDialog, QLabel, QLineEdit, QTableWidget, QTableWidgetItem, QTabWidget, QHeaderView
from PyQt5.QtCore import Qt  # Import Qt for table styling
from pymongo import MongoClient
import requests
from .ml_models import SubnetPredictionModel



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

        self.department_label = QLabel("Department:")
        self.department_input = QLineEdit()

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
        layout.addWidget(self.department_label)
        layout.addWidget(self.department_input)
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
            if num_hosts == None:
                num_hosts = 0
        department = self.department_input.text()

        # First, try to predict using the machine learning model
        try:
            predicted_subnet = self.subnet_model.predict_subnet(num_hosts, department)
            self.subnet_output.setText(f"Predicted Subnet: {predicted_subnet}")
        except Exception as e:
            print(f"ML Model prediction failed: {e}")
            # Fallback to basic logic if ML model fails
            predicted_subnet = self.subnet_model_predict(num_hosts, department)
            self.subnet_output.setText(f"Predicted Subnet: {predicted_subnet}")

    def subnet_model_predict(self, num_hosts, department):
        """Fallback logic for predicting subnet size based on department."""
        if department.lower() == "it":
            return "/24" if num_hosts <= 254 else "/16"
        elif department.lower() == "hr":
            return "/26" if num_hosts <= 62 else "/24"
        else:
            return "/28" if num_hosts <= 14 else "/24"

    def assign_ip(self):
        ip_address = self.ip_input.text()
        assigned_to = self.department_input.text()
        subnet = self.subnet_output.text().replace("Predicted Subnet: ", "")

        if ip_address and subnet and assigned_to:
            try:
                client = MongoClient('mongodb://localhost:27017/')
                db = client['ip_address_management']
                collection = db['ip_addresses']

                # Insert the new IP address document into MongoDB
                collection.insert_one({
                    'address': ip_address,
                    'subnet': subnet,
                    'assigned_to': assigned_to
                })

                # Clear input fields
                self.ip_input.clear()
                self.num_hosts_input.clear()
                self.department_input.clear()
                self.subnet_output.setText("---")

                QMessageBox.information(self, "Success", "IP Address assigned successfully!")
                self.accept()  # Close the dialog on success
            except Exception as e:
                QMessageBox.critical(self, "Database Error", f"Failed to assign IP address: {e}")
        else:
            QMessageBox.warning(self, "Input Error", "Please fill out all fields.")


class IPAddressManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IP Address Management")
        self.setGeometry(100, 100, 600, 400)

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
        self.search_button.clicked.connect(self.import_vlans)
        self.import_vlan_button = QPushButton("Import VLANs")
        self.import_vlan_button.clicked.connect(self.import_vlans)
        layout.addWidget(self.import_vlan_button)
        layout.addWidget(self.search_label)
        layout.addWidget(self.search_input)
        layout.addWidget(self.search_button)

        # Create a table to display VLANs and prefixes
        self.vlan_table = QTableWidget()
        self.vlan_table.setColumnCount(5)
        self.vlan_table.setHorizontalHeaderLabels(["VLAN Name", "VID", "Prefixes", "Status", "Description"])
        layout.addWidget(self.vlan_table)

        self.vlan_tab.setLayout(layout)

    def import_vlans(self):
        try:
            # Fetch VLAN data from NetBox
            base_url = 'https://netbox.cit.insea.io'
            headers = {
                'Authorization': 'Token e3d318664caba8355bcea30a00237ae38c02b357',  # Replace with your API token
            }

            # Step 1: Fetch VLANs
            vlan_url = f'{base_url}/api/ipam/vlans/?limit=5000'
            vlan_response = requests.get(vlan_url, headers=headers, verify=False)
            vlan_response.raise_for_status()
            vlans = vlan_response.json().get('results', [])

            # Clear current table rows
            self.vlan_table.setRowCount(0)

            # Iterate over VLANs and store each in the table
            for vlan in vlans:
                vlan_id = vlan['id']
                vlan_name = vlan['name']
                vlan_vid = vlan['vid']
                vlan_status = vlan['status']['label'] if 'status' in vlan else 'Unknown'
                vlan_description = vlan.get('description', 'No description')

                if self.search_input.text() not in vlan_name:
                    continue

                # Fetch prefixes for this VLAN
                prefixes_url = f'{base_url}/api/ipam/prefixes/?vlan_id={vlan_id}'
                prefix_response = requests.get(prefixes_url, headers=headers, verify=False)
                prefix_response.raise_for_status()
                prefixes = [prefix['prefix'] for prefix in prefix_response.json().get('results', [])]

                # Insert row in the table
                row_position = self.vlan_table.rowCount()
                self.vlan_table.insertRow(row_position)

                # Add data to table cells
                self.vlan_table.setItem(row_position, 0, QTableWidgetItem(vlan_name))
                self.vlan_table.setItem(row_position, 1, QTableWidgetItem(str(vlan_vid)))
                self.vlan_table.setItem(row_position, 2, QTableWidgetItem(", ".join(prefixes)))
                self.vlan_table.setItem(row_position, 3, QTableWidgetItem(vlan_status))
                self.vlan_table.setItem(row_position, 4, QTableWidgetItem(vlan_description))

            QMessageBox.information(self, "Success", "VLANs imported successfully!")

        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import VLANs: {e}")



    def update_ip_list(self):
        self.ip_table.setRowCount(0)  # Clear the current table

        try:
            client = MongoClient('mongodb://localhost:27017/')
            db = client['ip_address_management']
            collection = db['ip_addresses']

            # Fetch IP addresses, group them by department
            ip_addresses = list(collection.find({}, {'address': 1, 'subnet': 1, 'assigned_to': 1, '_id': 0}))
            ip_addresses.sort(key=lambda x: x['assigned_to'])  # Sort by department

            current_department = None
            row_position = 0

            # Check if list is empty
            if len(ip_addresses) == 0:
                self.ip_table.setRowCount(1)
                self.ip_table.setItem(0, 0, QTableWidgetItem("Nothing in database"))
                self.ip_table.setSpan(0, 0, 1, 3)
            else:
                for ip in ip_addresses:
                    department = ip.get('assigned_to', 'No Department')

                    # Add department header row
                    if department != current_department:
                        current_department = department
                        self.ip_table.insertRow(row_position)
                        department_item = QTableWidgetItem(f"Department: {current_department}")
                        department_item.setBackground(Qt.lightGray)  # Set department header background color
                        self.ip_table.setItem(row_position, 0, department_item)
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
    window = IPAddressManager()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
