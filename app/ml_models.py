import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error
import pandas as pd
from .db import ip_addresses  # Fetch historical data from MongoDB

class SubnetPredictionModel:
    def __init__(self):
        self.model = LinearRegression()

    def train_model(self):
        # Retrieve historical data from the database
        data = list(ip_addresses.find())  # Assuming your collection has historical data

        # Convert to pandas DataFrame for easier manipulation
        df = pd.DataFrame(data)

        # Extract features and target variable
        X = df[['num_hosts', 'department']]  # Example features
        y = df['subnet_size']  # Target (subnet size)

        # Convert categorical features (like department) to numerical
        X = pd.get_dummies(X)

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
        input_data = pd.DataFrame([[num_hosts, department]], columns=['num_hosts', 'department'])
        input_data = pd.get_dummies(input_data)

        # Make the prediction
        prediction = self.model.predict(input_data)
        return prediction[0]
