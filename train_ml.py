import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import datetime
import os
import joblib
import logging
from sklearn.ensemble import RandomForestClassifier
from math_models import KalmanFilterRegression
from data_ingestion import initialize_mt5, shutdown_mt5, get_rates_df, resolve_broker_symbol

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("train_ml")

def get_symbol_category(symbol: str) -> str:
    s = symbol.upper()
    if s.endswith("USDT") or any(x in s for x in ["BTC", "ETH", "SOL", "BNB", "AVAX", "XRP", "ADA", "DOGE", "MATIC", "LTC", "LINK", "DOT", "UNI", "SHIB"]):
        return "crypto"
    if any(x in s for x in ["XAU", "XAG"]):
        return "metals"
    if any(x in s for x in ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMD", "META", "AMZN", "US500", "US30", "NAS100", "GER30", "UK100"]):
        return "indices"
    return "forex"

def get_kf_parameters(symbol: str):
    cat = get_symbol_category(symbol)
    if cat == "crypto":
        return 1e-4, 1e4
    elif cat == "metals":
        return 1e-10, 1e3
    elif cat == "indices":
        return 1e-10, 1e5
    else: # forex/default
        return 1e-10, 1e-7

def get_pip_size(symbol: str) -> float:
    s = symbol.upper()
    if "JPY" in s:
        return 0.01
    if "XAU" in s:
        return 1.0
    if "XAG" in s:
        return 0.1
    if "BTC" in s:
        return 1.0
    if "ETH" in s:
        return 0.1
    if any(x in s for x in ["SOL", "BNB", "AVAX"]):
        return 0.01
    if any(x in s for x in ["XRP", "ADA", "DOGE", "MATIC"]):
        return 0.0001
    if any(x in s for x in ["US500", "US30", "NAS100", "GER30", "UK100", "SPX", "DJI", "NDX"]):
        return 1.0
    if any(x in s for x in ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMD", "META", "AMZN"]):
        return 0.1
    return 0.0001

def get_sl_distance(symbol: str, price: float, sl_pips: float) -> float:
    cat = get_symbol_category(symbol)
    if cat == "crypto":
        return float(price * (sl_pips / 100.0))
    else:
        return sl_pips * get_pip_size(symbol)

def fetch_db_active_pair():
    import psycopg2
    env_vars = {}
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    env_vars[k.strip()] = v.strip()
    conn_str = env_vars.get("DATABASE_URL")
    if not conn_str:
        return "XAUUSD/XAGUSD"
    try:
        conn = psycopg2.connect(conn_str)
        cur = conn.cursor()
        cur.execute("SELECT active_pair FROM bot_state LIMIT 1")
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row[0] if row else "XAUUSD/XAGUSD"
    except Exception as e:
        logger.warning(f"Failed to fetch active pair from DB: {e}")
        return "XAUUSD/XAGUSD"

def get_rates_dataframe(symbol, timeframe, count=3000):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    return df

def train_model():
    logger.info("Initializing MetaTrader 5 for historical data download...")
    if not mt5.initialize():
        logger.error(f"MT5 initialization failed: {mt5.last_error()}")
        return

    active_pair = fetch_db_active_pair()
    logger.info(f"Active pair for training: {active_pair}")
    parts = active_pair.split("/")
    if len(parts) != 2:
        logger.error("Invalid active pair format.")
        return
    
    s_a, s_b = parts[0], parts[1]
    s_a_res = resolve_broker_symbol(s_a)
    s_b_res = resolve_broker_symbol(s_b)

    logger.info(f"Downloading historical M5 candles for {s_a_res} and {s_b_res}...")
    df_a = get_rates_dataframe(s_a_res, mt5.TIMEFRAME_M5, count=4000)
    df_b = get_rates_dataframe(s_b_res, mt5.TIMEFRAME_M5, count=4000)

    if df_a is None or df_b is None:
        logger.error("Failed to retrieve rates data.")
        mt5.shutdown()
        return

    # Align indexes
    common_idx = df_a.index.intersection(df_b.index)
    df_a = df_a.loc[common_idx]
    df_b = df_b.loc[common_idx]

    logger.info(f"Aligned dataset size: {len(common_idx)} candles.")

    # Reconstruct Kalman spread
    q_cov, r_cov = get_kf_parameters(s_a)
    kf = KalmanFilterRegression(transition_covariance=q_cov, observation_covariance=r_cov)
    betas = []
    spreads = []
    z_scores = []
    z_velocities = []

    prices_a = (df_a['close'].values)
    prices_b = (df_b['close'].values)

    logger.info("Simulating Kalman Filter updates over history...")
    for i in range(len(common_idx)):
        p_a = prices_a[i]
        p_b = prices_b[i]
        beta, alpha, spread, z = kf.update(p_b, p_a)
        betas.append(beta)
        spreads.append(spread)
        z_scores.append(z)
        z_velocities.append(kf.get_velocity(k=3))

    df_data = pd.DataFrame(index=common_idx)
    df_data['price_a'] = prices_a
    df_data['price_b'] = prices_b
    df_data['high_a'] = df_a['high'].values
    df_data['low_a'] = df_a['low'].values
    df_data['high_b'] = df_b['high'].values
    df_data['low_b'] = df_b['low'].values
    df_data['beta'] = betas
    df_data['spread'] = spreads
    df_data['z_score'] = z_scores
    df_data['z_velocity'] = z_velocities
    df_data['hour'] = df_data.index.hour
    df_data['day_of_week'] = df_data.index.dayofweek

    # Simulate entries and outcomes
    features = []
    labels = []

    Z_ENTRY = 2.0
    Z_EXIT = 0.0
    SL_PIPS = 10.0  # Simulate standard SL

    logger.info("Labeling training samples (Success vs Failure)...")
    for i in range(100, len(df_data) - 100):
        z = df_data['z_score'].iloc[i]
        z_vel = df_data['z_velocity'].iloc[i]
        beta_val = df_data['beta'].iloc[i]
        spread_val = df_data['spread'].iloc[i]
        price_a = df_data['price_a'].iloc[i]
        price_b = df_data['price_b'].iloc[i]

        action = "NONE"
        if z < -Z_ENTRY:
            action = "BUY"
        elif z > Z_ENTRY:
            action = "SELL"

        if action != "NONE":
            # Determine Stop Loss distance
            sl_dist_a = get_sl_distance(s_a_res, price_a, SL_PIPS)
            sl_dist_b = get_sl_distance(s_b_res, price_b, SL_PIPS)

            sl_price_a = price_a - sl_dist_a if action == "BUY" else price_a + sl_dist_a
            sl_price_b = price_b + sl_dist_b if action == "BUY" else price_b - sl_dist_b

            # Simulate future candles
            outcome = None
            for j in range(i + 1, min(i + 150, len(df_data))):
                fut_z = df_data['z_score'].iloc[j]
                fut_high_a = df_data['high_a'].iloc[j]
                fut_low_a = df_data['low_a'].iloc[j]
                fut_high_b = df_data['high_b'].iloc[j]
                fut_low_b = df_data['low_b'].iloc[j]

                # Check if TP hit (spread reverted to mean)
                if (action == "BUY" and fut_z >= Z_EXIT) or (action == "SELL" and fut_z <= Z_EXIT):
                    outcome = 1  # Success
                    break

                # Check if SL hit using High/Low values
                hit_sl_a = (action == "BUY" and fut_low_a <= sl_price_a) or (action == "SELL" and fut_high_a >= sl_price_a)
                hit_sl_b = (action == "BUY" and fut_high_b >= sl_price_b) or (action == "SELL" and fut_low_b <= sl_price_b)

                if hit_sl_a or hit_sl_b:
                    outcome = 0  # Failure
                    break

            if outcome is not None:
                features.append([
                    z,
                    z_vel,
                    spread_val,
                    beta_val,
                    df_data['hour'].iloc[i],
                    df_data['day_of_week'].iloc[i]
                ])
                labels.append(outcome)

    features = np.array(features)
    labels = np.array(labels)

    if len(features) < 10:
        logger.error(f"Not enough training samples found (count: {len(features)}). Try increasing historical candles count.")
        mt5.shutdown()
        return

    logger.info(f"Total labeled samples: {len(features)} | Success rate: {np.mean(labels)*100:.1f}%")

    # Train Random Forest Classifier
    logger.info("Training Random Forest Classifier model...")
    clf = RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42)
    clf.fit(features, labels)

    # Save model
    model_path = "ml_model.joblib"
    joblib.dump(clf, model_path)
    logger.info(f"Model saved successfully to {model_path}!")

    mt5.shutdown()

if __name__ == "__main__":
    train_model()
