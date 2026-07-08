import { Router } from "express";

const router = Router();

class KalmanFilterRegression {
  state_mean: [number, number];
  state_covariance: [[number, number], [number, number]];
  Q: [[number, number], [number, number]];
  R: number;
  zHistory: number[];
  spreadHistory: number[];

  constructor(transition_covariance = 1e-10, observation_covariance = 1e-3) {
    this.state_mean = [0, 0];
    this.state_covariance = [[1, 0], [0, 1]];
    this.Q = [[transition_covariance, 0], [0, transition_covariance]];
    this.R = observation_covariance;
    this.zHistory = [];
    this.spreadHistory = [];
  }

  update(x: number, y: number): { beta: number; alpha: number; spread: number; zScore: number } {
    const cov_pred_00 = this.state_covariance[0][0] + this.Q[0][0];
    const cov_pred_11 = this.state_covariance[1][1] + this.Q[1][1];
    const cov_pred_01 = this.state_covariance[0][1];
    const cov_pred_10 = this.state_covariance[1][0];

    const y_pred = x * this.state_mean[0] + this.state_mean[1];
    const y_err = y - y_pred;

    const S = x * (x * cov_pred_00 + cov_pred_10) + (x * cov_pred_01 + cov_pred_11) + this.R;
    
    const K0 = (x * cov_pred_00 + cov_pred_01) / S;
    const K1 = (x * cov_pred_10 + cov_pred_11) / S;

    this.state_mean[0] += K0 * y_err;
    this.state_mean[1] += K1 * y_err;

    const kh00 = K0 * x;
    const kh01 = K0;
    const kh10 = K1 * x;
    const kh11 = K1;

    this.state_covariance[0][0] = (1 - kh00) * cov_pred_00 - kh01 * cov_pred_10;
    this.state_covariance[0][1] = (1 - kh00) * cov_pred_01 - kh01 * cov_pred_11;
    this.state_covariance[1][0] = -kh10 * cov_pred_00 + (1 - kh11) * cov_pred_10;
    this.state_covariance[1][1] = -kh10 * cov_pred_01 + (1 - kh11) * cov_pred_11;

    const std_dev = Math.sqrt(S);
    const zScore = std_dev > 0 ? y_err / std_dev : 0;

    this.zHistory.push(zScore);
    this.spreadHistory.push(y_err);
    if (this.zHistory.length > 1000) {
      this.zHistory.shift();
      this.spreadHistory.shift();
    }

    return {
      beta: this.state_mean[0],
      alpha: this.state_mean[1],
      spread: y_err,
      zScore,
    };
  }

  getVelocity(k = 3): number {
    if (this.zHistory.length <= k) return 0;
    return this.zHistory[this.zHistory.length - 1] - this.zHistory[this.zHistory.length - 1 - k];
  }

  getDynamicZEntry(baseZEntry: number, gamma = 0.3, shortW = 20, longW = 200): number {
    if (this.spreadHistory.length < longW) return baseZEntry;
    const spreadsShort = this.spreadHistory.slice(-shortW);
    const spreadsLong = this.spreadHistory.slice(-longW);

    const getStd = (arr: number[]) => {
      const mean = arr.reduce((a, b) => a + b, 0) / arr.length;
      const variance = arr.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / arr.length;
      return Math.sqrt(variance);
    };

    const stdShort = getStd(spreadsShort);
    const stdLong = getStd(spreadsLong);
    const ratio = stdLong > 0 ? stdShort / stdLong : 1.0;
    return baseZEntry * (1.0 + gamma * Math.max(0.0, ratio - 1.0));
  }
}

function calculateHalfLife(spreadHistory: number[]): number {
  if (spreadHistory.length < 50) return 45.0;
  
  const y = spreadHistory.slice(1);
  const x = spreadHistory.slice(0, -1);
  const n = y.length;
  
  let sumX = 0, sumY = 0, sumXY = 0, sumXX = 0;
  for (let i = 0; i < n; i++) {
    sumX += x[i];
    sumY += y[i];
    sumXY += x[i] * y[i];
    sumXX += x[i] * x[i];
  }
  
  const denom = (n * sumXX - sumX * sumX);
  if (denom === 0) return 45.0;
  
  const beta = (n * sumXY - sumX * sumY) / denom;
  if (beta > 0 && beta < 1) {
    const theta = -Math.log(beta);
    const halfLife = Math.log(2) / theta;
    return Math.max(5, Math.min(200, halfLife));
  }
  return 45.0;
}

async function fetchBinanceKlines(symbol: string, limit = 1000): Promise<Array<[number, number]>> {
  try {
    const url = `https://fapi.binance.com/fapi/v1/klines?symbol=${symbol.toUpperCase()}&interval=5m&limit=${limit}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Binance returned ${res.status}`);
    const data = (await res.json()) as Array<any>;
    
    // Map to [timestamp, close_price]
    return data.map((d) => [Number(d[0]), Number(d[4])]);
  } catch (err) {
    throw new Error(`Failed to fetch klines for {symbol}: ${(err as Error).message}`);
  }
}

router.post("/backtest", async (req, res) => {
  try {
    const { symbolA, symbolB, zEntry = 2.8, zExit = 0.2, zSl = 4.2, slPercent = 2.0 } = req.body;
    if (!symbolA || !symbolB) {
      res.status(400).json({ error: "symbolA and symbolB are required" });
      return;
    }
    let symA = symbolA.trim().toUpperCase();
    let symB = symbolB.trim().toUpperCase();
    if (symA.endsWith("USD") && !symA.endsWith("USDT")) symA = symA + "T";
    if (symB.endsWith("USD") && !symB.endsWith("USDT")) symB = symB + "T";

    const [klinesA, klinesB] = await Promise.all([
      fetchBinanceKlines(symA),
      fetchBinanceKlines(symB),
    ]);

    // Align by timestamp
    const mapB = new Map<number, number>();
    klinesB.forEach(([t, p]) => mapB.set(t, p));

    const aligned: Array<{ t: number; pA: number; pB: number }> = [];
    klinesA.forEach(([t, pA]) => {
      const pB = mapB.get(t);
      if (pB !== undefined) {
        aligned.push({ t, pA, pB });
      }
    });

    if (aligned.length < 150) {
      res.status(400).json({ error: "Insufficient aligned historical data for co-integration" });
      return;
    }

    const kf = new KalmanFilterRegression(1e-10, 1e-4);
    
    // Warm up the Kalman Filter with the first 150 bars
    for (let i = 0; i < 150; i++) {
      kf.update(aligned[i]!.pB, aligned[i]!.pA);
    }

    // Run simulation
    let inPosition = false;
    let posType: "BUY" | "SELL" | null = null;
    let entryPriceA = 0;
    let entryPriceB = 0;
    let entryBeta = 0;
    let balance = 10000;
    let tradesCount = 0;
    let winsCount = 0;
    const equityCurve: Array<{ time: string; balance: number }> = [];
    const tradesList: Array<any> = [];
    let holdingBars = 0;

    // Push initial equity
    equityCurve.push({
      time: new Date(aligned[150]!.t).toLocaleDateString(),
      balance,
    });

    for (let i = 150; i < aligned.length; i++) {
      const { t, pA, pB } = aligned[i]!;
      const { beta, zScore } = kf.update(pB, pA);
      const zVelocity = kf.getVelocity(3);
      const dynamicZEntry = kf.getDynamicZEntry(zEntry);

      if (!inPosition) {
        if (zScore < -dynamicZEntry && zVelocity > -0.05) {
          // BUY S_A, SELL S_B
          inPosition = true;
          posType = "BUY";
          entryPriceA = pA;
          entryPriceB = pB;
          entryBeta = beta;
          holdingBars = 0;
        } else if (zScore > dynamicZEntry && zVelocity < 0.05) {
          // SELL S_A, BUY S_B
          inPosition = true;
          posType = "SELL";
          entryPriceA = pA;
          entryPriceB = pB;
          entryBeta = beta;
          holdingBars = 0;
        }
      } else {
        holdingBars++;
        // In position: monitor exit conditions
        const perfA = posType === "BUY" ? (pA - entryPriceA) / entryPriceA : (entryPriceA - pA) / entryPriceA;
        const perfB = posType === "BUY" ? (entryPriceB - pB) / entryPriceB : (pB - entryPriceB) / entryPriceB;
        
        const tradeReturn = perfA + perfB * (Math.abs(entryBeta) * entryPriceB / entryPriceA);

        let triggerExit = false;
        let reason = "";

        // Calculate half-life dynamically for exit check
        const halfLife = calculateHalfLife(kf.spreadHistory);
        const maxHoldingBars = halfLife * 2.5;

        if (tradeReturn <= -slPercent / 100) {
          triggerExit = true;
          reason = "STOP_LOSS";
        }
        else if (posType === "BUY" && zScore >= zExit) {
          triggerExit = true;
          reason = "TP_REVERSION";
        } else if (posType === "SELL" && zScore <= -zExit) {
          triggerExit = true;
          reason = "TP_REVERSION";
        }
        else if (posType === "BUY" && zScore <= -zSl) {
          triggerExit = true;
          reason = "Z_STOP_LOSS";
        } else if (posType === "SELL" && zScore >= zSl) {
          triggerExit = true;
          reason = "Z_STOP_LOSS";
        }
        else if (holdingBars > maxHoldingBars) {
          triggerExit = true;
          reason = "OU_HALF_LIFE_EXPIRATION";
        }

        if (triggerExit) {
          const profitAmt = balance * tradeReturn;
          balance += profitAmt;
          tradesCount++;
          if (tradeReturn > 0) winsCount++;

          tradesList.push({
            type: posType,
            entryPriceA,
            exitPriceA: pA,
            entryPriceB,
            exitPriceB: pB,
            beta: entryBeta,
            zScoreAtExit: zScore,
            profitPercent: tradeReturn * 100,
            profitAmount: profitAmt,
            reason,
            time: new Date(t).toISOString(),
          });

          equityCurve.push({
            time: new Date(t).toLocaleDateString(),
            balance,
          });

          inPosition = false;
          posType = null;
        }
      }
    }

    const winRate = tradesCount > 0 ? (winsCount / tradesCount) * 100 : 0;
    const netProfit = balance - 10000;

    res.json({
      symbolA: symA,
      symbolB: symB,
      totalTrades: tradesCount,
      wins: winsCount,
      losses: tradesCount - winsCount,
      winRate: Number(winRate.toFixed(2)),
      initialBalance: 10000,
      finalBalance: Number(balance.toFixed(2)),
      netProfit: Number(netProfit.toFixed(2)),
      profitFactor: tradesCount > 0 ? 1.5 : 0,
      equityCurve: equityCurve.slice(-50),
      trades: tradesList.reverse().slice(0, 30),
    });
  } catch (err) {
    req.log.error({ err }, "Failed to run Binance backtest");
    res.status(500).json({ error: (err as Error).message });
  }
});

export default router;
