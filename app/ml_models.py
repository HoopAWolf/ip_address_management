import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error
import pandas as pd
from .db import ip_addresses  # Fetch historical data from MongoDB

valid_subnets = {
    2: "/30",
    6: "/29",
    14: "/28",
    30: "/27",
    62: "/26",
    126: "/25",
    254: "/24",
    510: "/23",
    1022: "/22",
    4094: "/20",
    16382: "/18",
    65534: "/16",
}

class SubnetPredictionModel:
    def __init__(self):
        self.model = LinearRegression()
        self.model_columns = []  # Initialize model_columns

    def calculate_hosts_from_subnet(self, subnet):
        if '/' in subnet:
            subnet_mask = int(subnet.split('/')[1])
            return 2**(32 - subnet_mask) - 2  # Exclude network and broadcast addresses
        else:
            return None

    def train_model(self):
        # Retrieve historical data from the database
        data = list(ip_addresses.find())

        if len(data) <= 0:
            print("Not enough data to train the model.")
            return

        # Convert to pandas DataFrame for easier manipulation
        df = pd.DataFrame(data)

        # Drop entries with missing 'subnet' or 'group' fields
        df = df.dropna(subset=['subnet', 'group'])

        # Calculate the number of hosts based on the subnet size
        df['num_hosts'] = df['subnet'].apply(self.calculate_hosts_from_subnet)

        # Use the number of hosts and group as features for training
        X = df[['num_hosts', 'group']]  # Features: num_hosts and group
        X = pd.get_dummies(X)  # Convert categorical 'group' into numerical values

        # Store the column names for later use
        self.model_columns = X.columns.tolist()

        y = df['subnet'].apply(self.calculate_hosts_from_subnet)  # Target: calculated number of hosts

        # Check if we have enough data to split into train/test sets
        if len(X) > 1:
            # Split the data into training and testing sets
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            
            # Train the model
            self.model.fit(X_train, y_train)

            # Evaluate the model
            y_pred = self.model.predict(X_test)
            error = mean_squared_error(y_test, y_pred)
            print(f"Model trained. Mean Squared Error: {error}")
        else:
            # Not enough data to split, train on the entire dataset
            self.model.fit(X, y)
            print("Model trained on the entire dataset (not enough data for test split).")


    def predict_subnet(self, num_hosts, group):
        """Predicts the subnet size based on input features."""
        # Prepare input features (ensure they match the training data format)
        input_data = pd.DataFrame([[num_hosts, group]], columns=['num_hosts', 'group'])
        input_data = pd.get_dummies(input_data)

        # Reindex the input DataFrame to ensure it has the same columns as the training DataFrame
        input_data = input_data.reindex(columns=self.model_columns, fill_value=0)

        # Make the prediction
        prediction = self.model.predict(input_data)
        
        # Find the closest valid subnet size
        closest_subnet = min(valid_subnets.keys(), key=lambda x: abs(x - prediction[0]))

        return valid_subnets[closest_subnet]

