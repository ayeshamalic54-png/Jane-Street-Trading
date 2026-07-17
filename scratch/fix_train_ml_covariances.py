import os

train_path = os.path.join(os.path.dirname(__file__), "..", "train_ml.py")

with open(train_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add get_kf_parameters definition below get_pip_size
old_target = """def get_pip_size(symbol: str) -> float:"""

kf_params_def = """def get_kf_parameters(symbol: str):
    cat = get_symbol_category(symbol)
    if cat == "crypto":
        return 1e-4, 1e4
    elif cat == "metals":
        return 1e-10, 1e3
    elif cat == "indices":
        return 1e-10, 1e5
    else: # forex/default
        return 1e-10, 1e-7

"""

content = content.replace(old_target, kf_params_def + old_target)

# 2. Update KalmanFilterRegression initialization in train_model
old_kf_init = "    kf = KalmanFilterRegression(transition_covariance=1e-4, observation_covariance=1e-4)"
new_kf_init = """    q_cov, r_cov = get_kf_parameters(s_a)
    kf = KalmanFilterRegression(transition_covariance=q_cov, observation_covariance=r_cov)"""

content = content.replace(old_kf_init, new_kf_init)

with open(train_path, "w", encoding="utf-8") as f:
    f.write(content)
print("train_ml.py updated with correct Kalman filter covariances matching main.py.")
