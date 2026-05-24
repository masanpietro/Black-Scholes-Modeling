# Black-Scholes Python Algorithm with Trading Sim and TWAP Execution

A Python-based Black-Scholes model designed to identify and exploit structural inefficiencies in undertraded options markets. 

This script dynamically prices options using the Black-Scholes model, compares theoretical values against a simulated live data stream, and executes automated statistical arbitrage strategies using a Time-Weighted Average Price (TWAP) algorithm to mitigate slippage.

## Core Architecture

The script has four primary components:

* **Pricing Engine:** A lightweight, dependency-free implementation of the Black-Scholes European option pricing model. Uses built-in standard error functions (math.erf) to approximate the Normal CDF.
*  **Mock Market Streamer:** Generates synthetic tick data mimicking a live institutional websocket. Simulates stock price movement using Geometric Brownian Motion (Gaussian returns generating Lognormal prices) and mimics the volatile Bid-Ask spreads characteristic of low-volume, mid-cap equities.
* **Portfolio Manager:** Tracks real-time cash balances, calculates cost bases using weighted averages, and logs realized profits and losses for individual arbitrage trades.
* **Execution Algorithms (TWAP):** Protects the strategy's theoretical edge by slicing large market-moving orders into smaller batches. This prevents any possible slippage which may occur in undertraded(mildly illiquid) options markets.

## Mathematical Foundations

* **Lognormal Price Distribution:** The data streamer generates market movement by applying normally distributed percentage returns to the underlying asset, adhering to the core random walk (Wiener process) assumptions of the Black-Scholes model.
* **Volatility Edge:** The strategy relies on decoupling historical/forecasted volatility from the market's Implied Volatility (IV). The engine triggers execution when the quoted market price implies a volatility significantly lower than the model's proprietary forecast.
