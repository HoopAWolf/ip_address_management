import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error
import pandas as pd
from .db import ip_addresses  # Fetch historical data from MongoDB

class SubnetPredictionModel:
    def __init__(self):
        self.model = LinearRegression()

    def calculate_hosts_from_subnet(self, subnet):
        # Convert subnet to number of hosts (simple approximation)
        # Example: /24 -> 254 hosts, /16 -> 65534 hosts
        if '/' in subnet:
            subnet_mask = int(subnet.split('/')[1])
            return 2**(32 - subnet_mask) - 2  # Exclude network and broadcast addresses
        else:
            return None

    def train_model(self):
        # Retrieve historical data from the database
        data = list(ip_addresses.find())

        # Convert to pandas DataFrame for easier manipulation
        df = pd.DataFrame(data)

        # Drop entries with missing 'subnet' or 'assigned_to' fields
        df = df.dropna(subset=['subnet', 'assigned_to'])

        # Calculate the number of hosts based on the subnet size
        df['num_hosts'] = df['subnet'].apply(self.calculate_hosts_from_subnet)

        # Use the number of hosts and department as features for training
        X = df[['num_hosts', 'assigned_to']]  # Features: num_hosts and assigned department
        X = pd.get_dummies(X)  # Convert categorical 'assigned_to' (department) into numerical values

        y = df['subnet'].apply(self.calculate_hosts_from_subnet)  # Target: calculated number of hosts

        # Split the data into training and testing sets
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # Train the model
        self.model.fit(X_train, y_train)

        # Evaluate the model
        y_pred = self.model.predict(X_test)
        error = mean_squared_error(y_test, y_pred)
        print(f"Model trained. Mean Squared Error: {error}")

    def predict_subnet(self, num_hosts, department):
        """Predicts the subnet size based on input features."""
        # Prepare input features (ensure they match the training data format)
        input_data = pd.DataFrame([[num_hosts, department]], columns=['num_hosts', 'assigned_to'])
        input_data = pd.get_dummies(input_data)

        # Make the prediction
        prediction = self.model.predict(input_data)
        return prediction[0]
