import math
import time
import random
from typing import Dict, List

#pricing engine
def norm_cdf(x: float) -> float:
    #Exact CDF for standard normal distribution using error function
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0

def black_scholes_price(S: float, K: float, T_days: float, r: float, sigma: float, option_type: str = "call") -> float:
    # Theorecial price of a European call or put option using the Black-Scholes formula
    T = T_days / 365.0
    if T <= 0:
        return max(0.0, S - K) if option_type == "call" else max(0.0, K - S)

    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    if option_type == "call":
        return S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
    else:
        return K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)

#portfolio management
class Portfolio:
    def __init__(self, initial_cash: float = 1_000_000.0):
        self.cash = initial_cash
        self.positions: Dict[str, dict] = {}
        self.realized_pnl = 0.0

    def buy_option(self, symbol: str, price: float, quantity: int, theoretical_edge: float):
        cost = price * quantity * 100 # Options multiplier
        if self.cash >= cost:
            self.cash -= cost
            if symbol in self.positions:
                # Average down cost basis
                old_qty = self.positions[symbol]['qty']
                old_cost = self.positions[symbol]['avg_price']
                new_avg = ((old_qty * old_cost) + (quantity * price)) / (old_qty + quantity)
                self.positions[symbol]['qty'] += quantity
                self.positions[symbol]['avg_price'] = new_avg
            else:
                self.positions[symbol] = {'qty': quantity, 'avg_price': price}
            
            print(f"      [PORTFOLIO] Executed {quantity} {symbol} @ ${price:.2f} | Cash: ${self.cash:,.2f}")
        else:
            print(f"      [PORTFOLIO] Insufficient cash to buy {quantity} {symbol} @ ${price:.2f} | Cash: ${self.cash:,.2f}")

    def sell_option(self, symbol: str, price: float, quantity: int):
        if symbol in self.positions and self.positions[symbol]['qty'] >= quantity:
            revenue = price * quantity * 100
            self.cash += revenue
            
            cost_basis = self.positions[symbol]['avg_price'] * quantity * 100
            trade_pnl = revenue - cost_basis
            self.realized_pnl += trade_pnl
            
            self.positions[symbol]['qty'] -= quantity
            if self.positions[symbol]['qty'] == 0:
                del self.positions[symbol]
                
            print(f"[PORTFOLIO] EXIT: Sold {quantity} {symbol} @ ${price:.2f} | Trade PnL: ${trade_pnl:,.2f}")
        else:
            print(f"[PORTFOLIO] Cannot sell {quantity} {symbol} @ ${price:.2f} | Not enough quantity or position doesn't exist")

    def print_summary(self):
        print("\n" + "="*55)
        print("PORTFOLIO SUMMARY")
        print("="*55)
        print(f"Ending Cash:    ${self.cash:,.2f}")
        print(f"Realized PnL:   ${self.realized_pnl:,.2f}")
        print(f"Open Positions: {self.positions}")
        print("="*55 + "\n")

#mock market stream 
class MockMarketStream:
    #Simulates a live institutional tick data stream.
    def __init__(self):
        self.current_stock_price = 180.00
        self.r = 0.0525 # 1-Month T-Bill
        
    def get_next_tick(self):
        # Simulate a random walk for the stock price
        self.current_stock_price *= (1 + random.gauss(0, 0.002))
        
        # Simulate market IV fluctuating due to low volume
        iv = max(0.10, random.gauss(0.25, 0.05)) 
        
        # Calculate base theoretical price and add random tracking error for spread
        theo_price = black_scholes_price(self.current_stock_price, 180.0, 30.0, self.r, iv, "call")
        market_spread = theo_price * random.uniform(0.80, 1.20) 
        
        return {
            "symbol": "TEST",
            "stock_price": self.current_stock_price,
            "opt_symbol": "TEST_260619C00180000",
            "strike": 180.0,
            "dte": 30.0,
            "market_iv": iv,
            "market_ask": round(market_spread * 1.03, 2), # Wide ask spread
            "market_bid": round(market_spread * 0.97, 2), # Wide bid spread
            "risk_free_rate": self.r
        }

#twap trade execution
def execute_twap_buy(symbol: str, total_qty: int, slices: int, max_price: float, portfolio: Portfolio, stream: MockMarketStream):
    """
    Takes control of the data stream to execute a large order in pieces,
    checking live prices against a hard limit before each slice.
    """
    qty_per_slice = total_qty // slices
    print(f"\n   >>> [TWAP INITIATED] Order: {total_qty} {symbol}")
    print(f"   >>> [TWAP PARAMS] {slices} slices of {qty_per_slice} | Max Limit: ${max_price:.2f}")
    
    filled_qty = 0
    
    for i in range(slices):
        # Pull a fresh tick from the market while the TWAP is running
        tick = stream.get_next_tick()
        current_ask = tick["market_ask"]
        
        if current_ask <= max_price:
            portfolio.buy_option(symbol, current_ask, qty_per_slice, theoretical_edge=(max_price - current_ask))
            filled_qty += qty_per_slice
            print(f"   ---> [TWAP {i+1}/{slices}] Filled @ ${current_ask:.2f} (Stock at ${tick['stock_price']:.2f})")
        else:
            print(f"   ---> [TWAP {i+1}/{slices}] Paused. Current Ask ${current_ask:.2f} exceeds limit ${max_price:.2f}")
            
        # Simulate the wait time between slices to let the order book refill
        time.sleep(0.4) 
        
    print(f"   >>> [TWAP COMPLETE] Total Filled: {filled_qty}/{total_qty}\n")
    return tick # Return the final state of the market to the main loop

#trading bot
def run_volatility_arbitrage_bot(search_ticks=25):
    portfolio = Portfolio(initial_cash=1_000_000.0)
    stream = MockMarketStream()
    
    # Strategy Weights
    EDGE_THRESHOLD = 0.15  # Require 15% discount to theoretical price to trigger an entry
    PROFIT_TARGET = 1.15   # Sell if Bid exceeds our cost basis by 15%
    PROPRIETARY_IV = 0.22  # Our static, forecasted volatility model
    ORDER_SIZE = 50        # Total contracts to buy per signal
    TWAP_SLICES = 5        # Break order into 5 pieces of 10 contracts
    
    print("Initializing Quantitative Arbitrage Engine...")
    print(f"Targeting: TEST | Strategy: Stat-Arb with TWAP Execution\n")
    
    for i in range(search_ticks):
        tick = stream.get_next_tick()
        opt_sym = tick["opt_symbol"]
        
        # 1. Price the option using Black-Scholes model and compare to market price to find mispricings
        my_theo_price = black_scholes_price(
            S=tick["stock_price"], 
            K=tick["strike"], 
            T_days=tick["dte"], 
            r=tick["risk_free_rate"], 
            sigma=PROPRIETARY_IV 
        )
        
        market_price = tick["market_ask"]
        discount = (my_theo_price - market_price) / my_theo_price if my_theo_price > 0 else 0
        
        print(f"Tick {i+1:02d} | TEST: ${tick['stock_price']:.2f} | Theo: ${my_theo_price:.2f} | Ask: ${market_price:.2f} | Edge: {discount*100:.1f}%")
        
        # If the market maker misprices the option by > 15%, trigger TWAP
        if discount > EDGE_THRESHOLD and market_price > 0.50:
            # Set absulute max limit price to guarantee 10%$ edge 
            max_acceptable_price = my_theo_price * 0.90 
            
            # Pass the stream to the TWAP executor so it can pull live prices during the execution
            tick = execute_twap_buy(opt_sym, ORDER_SIZE, TWAP_SLICES, max_acceptable_price, portfolio, stream)
            
        # Check if any open positions hit profit target
        if opt_sym in portfolio.positions:
            avg_cost = portfolio.positions[opt_sym]['avg_price']
            current_bid = tick["market_bid"]
            
            if current_bid >= avg_cost * PROFIT_TARGET:
                qty_to_sell = portfolio.positions[opt_sym]['qty']
                print(f"\n*** PROFIT TARGET REACHED: Bid hit ${current_bid:.2f} (Avg Cost: ${avg_cost:.2f}) ***")
                portfolio.sell_option(opt_sym, current_bid, quantity=qty_to_sell)
                print()
                
        time.sleep(0.1) # Simulate delay between main loop data checks
        
    portfolio.print_summary()

if __name__ == "__main__":
    #search_ticks controls how long the bot runs (how many market ticks it processes)
    run_volatility_arbitrage_bot(search_ticks=1000)