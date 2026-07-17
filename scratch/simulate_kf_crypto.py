import numpy as np

class KalmanFilterRegression:
    def __init__(self, transition_covariance, observation_covariance):
        self.Q = transition_covariance
        self.R = observation_covariance
        self.x = np.zeros((2, 1)) # state [beta, alpha]^T
        self.P = np.eye(2) * 10.0 # covariance
        self.spread_history = []
        self.z_history = []

    def update(self, y, x_val):
        # y = beta * x_val + alpha
        H = np.array([[x_val, 1.0]])
        
        # Predict
        self.P = self.P + np.eye(2) * self.Q
        
        # Update
        S = H.dot(self.P).dot(H.T) + self.R
        K = self.P.dot(H.T) / S
        y_err = y - H.dot(self.x)[0, 0]
        self.x = self.x + K * y_err
        self.P = (np.eye(2) - K.dot(H)) * self.P
        
        # Calculate standard deviation of spread for Z-score
        self.spread_history.append(float(y_err))
        if len(self.spread_history) > 1:
            std_dev = np.std(self.spread_history[-30:])
        else:
            std_dev = 1.0
            
        z_score = y_err / std_dev if std_dev > 0 else 0.0
        self.z_history.append(z_score)
        return self.x[0, 0], self.x[1, 0], y_err, z_score

# Simulate with mock crypto prices: Leg A goes up from 100 to 110, Leg B stays at 10
prices_a = [100.0 + i * 0.5 for i in range(20)]
prices_b = [10.0] * 20

print("=== SETTING 1 (CURRENT CRYPTO: Q=1e-4, R=1e4) ===")
kf1 = KalmanFilterRegression(1e-4, 1e4)
for pa, pb in zip(prices_a, prices_b):
    beta, alpha, spread, z = kf1.update(pa, pb)
    print(f"PriceA: {pa} | Beta: {beta:.4f} | Spread: {spread:.4f} | Z-score: {z:.4f}")

print("\n=== SETTING 2 (PROPOSED CRYPTO: Q=1e-8, R=1e-5) ===")
kf2 = KalmanFilterRegression(1e-8, 1e-5)
for pa, pb in zip(prices_a, prices_b):
    beta, alpha, spread, z = kf2.update(pa, pb)
    print(f"PriceA: {pa} | Beta: {beta:.4f} | Spread: {spread:.4f} | Z-score: {z:.4f}")
