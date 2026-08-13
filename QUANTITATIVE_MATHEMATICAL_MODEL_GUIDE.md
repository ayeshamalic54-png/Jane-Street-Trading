# 📐 Jane Street Quantum Trading Engine: Mathematical Model & Architecture Guide

Welcome to the comprehensive technical documentation for the **Jane Street Quantum Engine**. This document outlines the advanced mathematical framework, econometrics, statistical arbitrage models, and risk safeguards power-housing our institutional-grade automated trading system.

---

## 🏛️ Executive Summary

The **Jane Street Quantum Trading System** is a High-Frequency Statistical Arbitrage (StatArb) engine designed to exploit mean-reverting price spreads between highly co-integrated asset pairs (e.g. `EURUSD/USDCHF`, `GBPUSD/USDCHF`, `XAUUSD/XAGUSD`). 

Instead of traditional directional technical analysis (RSI, Moving Averages), the engine utilizes **Kalman Filtering, Stochastic Differential Equations, Matrix Calculus, and Time-Series Econometrics** to capture mathematical mispricings with zero directional bias.

---

## 🧮 The 5 Advanced Mathematical Pillars

### 1. Linear Algebra & Matrix Operations (State-Space Models)
The relationship between trading pairs is dynamic and changes over time. We model the hedge ratio $\beta_t$ using a discrete-time State-Space model:

$$\boldsymbol{\theta}_t = \boldsymbol{\theta}_{t-1} + \boldsymbol{w}_t \quad (\boldsymbol{w}_t \sim \mathcal{N}(0, \mathbf{Q})) \quad \text{[State Equation]}$$

$$y_t = \mathbf{x}_t^T \boldsymbol{\theta}_t + v_t \quad (v_t \sim \mathcal{N}(0, R)) \quad \text{[Observation Equation]}$$

* **Implementation in Code**: `kalman_filter.py` / `main.py`
* **Purpose**: Live updates of state vector $\boldsymbol{\theta}_t = [\beta_t, \alpha_t]^T$ and covariance matrix $\mathbf{P}_t$ using NumPy array operations.

---

### 2. Matrix Calculus & Kalman Optimization
To estimate the true underlying spread without lagging traditional moving averages, we calculate the optimal **Kalman Gain matrix** $K_t$:

$$\mathbf{K}_t = \mathbf{P}_{t|t-1} \mathbf{x}_t \left(\mathbf{x}_t^T \mathbf{P}_{t|t-1} \mathbf{x}_t + R\right)^{-1}$$

$$\boldsymbol{\theta}_{t|t} = \boldsymbol{\theta}_{t|t-1} + \mathbf{K}_t \left(y_t - \mathbf{x}_t^T \boldsymbol{\theta}_{t|t-1}\right)$$

$$\mathbf{P}_{t|t} = \left(\mathbf{I} - \mathbf{K}_t \mathbf{x}_t^T\right) \mathbf{P}_{t|t-1}$$

* **Purpose**: Minimizes the Mean Squared Error (MSE) of estimation in real-time, removing market noise while tracking rapid regime shifts.

---

### 3. Stochastic Differential Equations (SDE) & Ornstein-Uhlenbeck (OU) Process
Spread mean reversion is modeled as a continuous-time Ornstein-Uhlenbeck stochastic process:

$$dX_t = \theta (\mu - X_t) dt + \sigma dW_t$$

Where:
* $X_t$ = Current spread price
* $\theta$ = Speed of mean reversion
* $\mu$ = Long-term mean spread
* $dW_t$ = Standard Brownian motion (Wiener process)

**Half-Life Calculation ($\tau$)**:
$$\tau = \frac{\ln(2)}{\theta}$$

* **Purpose**: Determines the statistical time (in minutes) required for the spread to decay back to equilibrium by 50%. Used for time-based exit execution.

---

### 4. Time-Series Econometrics (Engle-Granger & ADF Tests)
Before executing spread signals, pairs are tested for long-term co-integration using the **Engle-Granger Two-Step Method** and **Augmented Dickey-Fuller (ADF) Unit Root Test**:

$$\Delta y_t = \alpha + \beta t + \gamma y_{t-1} + \sum_{i=1}^{p} \delta_i \Delta y_{t-i} + \epsilon_t$$

* **Null Hypothesis ($H_0$)**: $\gamma = 0$ (Spread has a unit root / non-stationary).
* **Alternative ($H_1$)**: $\gamma < 0$ (Spread is stationary $I(0)$).
* **Purpose**: Ensures trades are only placed when pairs are mathematically bound to revert.

---

### 5. Probability Theory & Gaussian Normal Distributions ($Z$-Scores)
The system normalizes spread deviations into a Standard Normal Distribution $\mathcal{N}(0, 1)$:

$$Z_t = \frac{\text{Spread}_t - \mu_{\text{Kalman}}}{\sigma_{\text{Rolling}}}$$

* **Entry Logic**:
  * **$Z \ge +2.30$**: Spread is at upper 98.9% extreme quantile $\rightarrow$ **SELL Spread** (Sell Leg A, Buy Leg B).
  * **$Z \le -2.30$**: Spread is at lower 98.9% extreme quantile $\rightarrow$ **BUY Spread** (Buy Leg A, Sell Leg B).

---

## 🛡️ Multi-Layer Institutional Risk Safeguards

### 1. Multi-Tier Equity Profit Lock Guard (Dual Tier)
* **Tier 1 (Safety Floor at +$50 Peak)**: When peak profit hits $+\$50.00$ to $+\$99.00$, activates a $+\$35.00$ safety floor. If market reverses, auto-closes at $+\$35.00+$ to guarantee ZERO loss!
* **Tier 2 (Full Trailing Stop at +$100+ Peak)**: When peak profit hits $+\$100.00+$, locks 91% of peak earnings ($+\$91.00$ to $\$900+$).

### 2. Friday Weekend Close Guard (Sunday Gap Elimination)
* Automatically triggers at **Friday 4:15 PM EST** (45 minutes before market close).
* **Action 1**: Closes all open positions at market price.
* **Action 2**: Blocks new trade entries for the rest of Friday.
* **Result**: Zero positions held over the weekend $\rightarrow$ **0% Sunday Opening Price Gap Risk**.

### 3. 15-Minute High-Impact News Guard
* Monitors economic calendar feeds for high-impact USD/EUR news.
* Blocks new entries 15 minutes before news releases while letting active trailing stops manage running trades.

### 4. Maximum Daily Drawdown Guard
* Hard limit set to **3.2% max daily loss** (safely below Prop Firm 4.0% limits).

---

## 📂 Codebase File Mapping

| Component | File Path | Responsibilities |
|---|---|---|
| **Main Engine & Loop** | `trading/bot/main.py` | Z-score calculation, trade execution, trailing stop, Friday guard |
| **Kalman Filter** | `trading/bot/kalman_filter.py` | Matrix operations, state-space vector updates, covariance matrices |
| **Database Sync** | `trading/bot/database.py` | PostgreSQL persistence, bot_state, daily_metrics, deadlock retries |
| **Risk Safeguards** | `trading/bot/risk_safeguards.py` | Daily drawdown verification, lot size safety checks |
| **News Guard** | `trading/bot/news_guard.py` | High-impact economic news detection & buffer checks |

---

## 🚀 Deployment & VPS Synchronization

To pull and apply the latest mathematical model updates on your VPS:

```bash
git fetch origin && git reset --hard origin/main
```

*Documentation created: 03/08/2026*  
*Jane Street Quantum Engine Architecture v2.4*
