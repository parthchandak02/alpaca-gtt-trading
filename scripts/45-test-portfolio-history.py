#!/usr/bin/env python3
"""Test script for Portfolio History API endpoints.

Tests:
1. Portfolio history endpoint with different periods
2. Portfolio P/L summary for Today/Weekly/Monthly/Yearly/All-Time
3. Data accuracy and formatting

Run with: uv run --directory backend scripts/45-test-portfolio-history.py
"""
import sys
import os
import logging
import requests
import json
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from config import settings

# Test configuration
BACKEND_URL = "http://localhost:8000"


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_result(test_name: str, passed: bool, details: str = ""):
    """Print test result."""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}: {test_name}")
    if details:
        print(f"  {details}")


def test_portfolio_history_raw():
    """Test raw portfolio history endpoint."""
    print_section("TEST 1: Raw Portfolio History Endpoint")
    
    try:
        # Test 1D period with 1D timeframe
        url = f"{BACKEND_URL}/api/portfolio-history"
        params = {
            "period": "1D",
            "timeframe": "1D",
        }
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # Validate response structure
        required_fields = ["timestamp", "equity", "profit_loss", "profit_loss_pct", "base_value", "timeframe"]
        missing_fields = [f for f in required_fields if f not in data]
        
        if missing_fields:
            print_result("Raw portfolio history structure", False, f"Missing fields: {missing_fields}")
            return False
        
        # Validate data types
        if not isinstance(data["timestamp"], list):
            print_result("Timestamp array", False, f"Expected list, got {type(data['timestamp'])}")
            return False
        
        if not isinstance(data["equity"], list):
            print_result("Equity array", False, f"Expected list, got {type(data['equity'])}")
            return False
        
        if len(data["equity"]) > 0:
            print_result("Raw portfolio history", True, 
                        f"Got {len(data['equity'])} data points, timeframe={data['timeframe']}, "
                        f"base_value=${data['base_value']:.2f}")
            
            # Show first and last data points
            if len(data["equity"]) >= 2:
                first_equity = data["equity"][0]
                last_equity = data["equity"][-1]
                first_pl = data["profit_loss"][0] if data["profit_loss"] else 0
                last_pl = data["profit_loss"][-1] if data["profit_loss"] else 0
                print(f"  First: equity=${first_equity:.2f}, P/L=${first_pl:.2f}")
                print(f"  Last:  equity=${last_equity:.2f}, P/L=${last_pl:.2f}")
        else:
            print_result("Raw portfolio history", True, "No data points (account may be new)")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print_result("Raw portfolio history", False, f"Request error: {e}")
        return False
    except Exception as e:
        print_result("Raw portfolio history", False, f"Error: {e}")
        return False


def test_portfolio_pl_summary(period: str):
    """Test portfolio P/L summary for a specific period."""
    try:
        url = f"{BACKEND_URL}/api/portfolio-pl"
        params = {"period": period}
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # Validate response structure
        required_fields = ["period", "profit_loss_dollars", "profit_loss_percent", "equity", "base_value", "data_points"]
        missing_fields = [f for f in required_fields if f not in data]
        
        if missing_fields:
            print_result(f"P/L summary structure ({period})", False, f"Missing fields: {missing_fields}")
            return False
        
        # Validate period matches request
        if data["period"] != period:
            print_result(f"P/L summary period ({period})", False, 
                        f"Expected {period}, got {data['period']}")
            return False
        
        # Format output
        pl_dollars = data["profit_loss_dollars"]
        pl_percent = data["profit_loss_percent"]
        equity = data["equity"]
        base_value = data["base_value"]
        data_points = data["data_points"]
        
        pl_sign = "+" if pl_dollars >= 0 else ""
        percent_sign = "+" if pl_percent >= 0 else ""
        
        print_result(
            f"P/L Summary ({period})",
            True,
            f"P/L: {pl_sign}${pl_dollars:.2f} ({percent_sign}{pl_percent:.2f}%), "
            f"Equity: ${equity:.2f}, Base: ${base_value:.2f}, Points: {data_points}"
        )
        
        return True
        
    except requests.exceptions.RequestException as e:
        print_result(f"P/L summary ({period})", False, f"Request error: {e}")
        return False
    except Exception as e:
        print_result(f"P/L summary ({period})", False, f"Error: {e}")
        return False


def test_all_periods():
    """Test all P/L summary periods."""
    print_section("TEST 2: Portfolio P/L Summary (All Periods)")
    
    periods = ["today", "weekly", "monthly", "yearly", "all_time"]
    results = []
    
    for period in periods:
        result = test_portfolio_pl_summary(period)
        results.append((period, result))
        # Small delay between requests to avoid rate limiting
        import time
        time.sleep(0.5)
    
    # Summary
    passed = sum(1 for _, r in results if r)
    total = len(results)
    print(f"\nSummary: {passed}/{total} periods passed")
    
    return all(r for _, r in results)


def test_portfolio_chart_data():
    """Test portfolio history for chart data."""
    print_section("TEST 3: Portfolio Chart Data")
    
    try:
        # Get 30 days of daily data for chart
        url = f"{BACKEND_URL}/api/portfolio-history"
        params = {
            "period": "30D",
            "timeframe": "1D",
        }
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        equity_data = data.get("equity", [])
        timestamp_data = data.get("timestamp", [])
        
        if len(equity_data) == 0:
            print_result("Chart data", True, "No data available (account may be new)")
            return True
        
        # Validate data for charting
        if len(equity_data) != len(timestamp_data):
            print_result("Chart data consistency", False, 
                        f"Equity ({len(equity_data)}) and timestamp ({len(timestamp_data)}) arrays don't match")
            return False
        
        # Show sample data points
        print_result("Chart data", True, 
                    f"Got {len(equity_data)} data points for chart")
        
        # Show first 3 and last 3 data points
        print("\n  Sample data points:")
        sample_indices = list(range(min(3, len(equity_data))))
        if len(equity_data) > 6:
            sample_indices.extend(range(len(equity_data) - 3, len(equity_data)))
        else:
            sample_indices = list(range(len(equity_data)))
        
        for idx in sample_indices:
            ts = timestamp_data[idx]
            eq = equity_data[idx]
            pl = data["profit_loss"][idx] if data.get("profit_loss") and idx < len(data["profit_loss"]) else 0
            pl_pct = data["profit_loss_pct"][idx] if data.get("profit_loss_pct") and idx < len(data["profit_loss_pct"]) else 0
            
            # Convert timestamp to readable date
            dt = datetime.fromtimestamp(ts)
            pl_sign = "+" if pl >= 0 else ""
            pct_sign = "+" if pl_pct >= 0 else ""
            
            print(f"    {dt.strftime('%Y-%m-%d')}: Equity=${eq:.2f}, "
                  f"P/L={pl_sign}${pl:.2f} ({pct_sign}{pl_pct:.2f}%)")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print_result("Chart data", False, f"Request error: {e}")
        return False
    except Exception as e:
        print_result("Chart data", False, f"Error: {e}")
        return False


def test_today_pl_vs_account():
    """Test that today's P/L matches account data calculation."""
    print_section("TEST 4: Today's P/L vs Account Data")
    
    try:
        # Get account data
        account_url = f"{BACKEND_URL}/api/account"
        account_response = requests.get(account_url, timeout=10)
        account_response.raise_for_status()
        account_data = account_response.json()
        
        equity = account_data.get("equity", 0.0)
        last_equity = account_data.get("last_equity")
        
        # Get today's P/L from portfolio-pl endpoint
        pl_url = f"{BACKEND_URL}/api/portfolio-pl"
        pl_response = requests.get(pl_url, params={"period": "today"}, timeout=10)
        pl_response.raise_for_status()
        pl_data = pl_response.json()
        
        if last_equity is None or last_equity == 0:
            print_result("Today's P/L calculation", True, 
                        "No last_equity available (account may be new)")
            return True
        
        # Calculate expected P/L
        expected_pl_dollars = equity - last_equity
        expected_pl_percent = ((equity - last_equity) / last_equity * 100) if last_equity > 0 else 0.0
        
        # Compare (allow small floating point differences)
        pl_dollars_diff = abs(pl_data["profit_loss_dollars"] - expected_pl_dollars)
        pl_percent_diff = abs(pl_data["profit_loss_percent"] - expected_pl_percent)
        
        tolerance = 0.01  # $0.01 or 0.01% tolerance
        
        if pl_dollars_diff > tolerance or pl_percent_diff > tolerance:
            print_result("Today's P/L calculation", False,
                        f"P/L mismatch: Expected ${expected_pl_dollars:.2f} ({expected_pl_percent:.2f}%), "
                        f"Got ${pl_data['profit_loss_dollars']:.2f} ({pl_data['profit_loss_percent']:.2f}%)")
            return False
        
        print_result("Today's P/L calculation", True,
                    f"Matches account data: ${pl_data['profit_loss_dollars']:.2f} "
                    f"({pl_data['profit_loss_percent']:.2f}%)")
        return True
        
    except Exception as e:
        print_result("Today's P/L calculation", False, f"Error: {e}")
        return False


def test_account_summary_calculations():
    """Test account summary field relationships and calculations."""
    print_section("TEST 5: Account Summary Calculations")
    
    try:
        # Get account data
        account_url = f"{BACKEND_URL}/api/account"
        account_response = requests.get(account_url, timeout=10)
        account_response.raise_for_status()
        account_data = account_response.json()
        
        # Get positions
        positions_url = f"{BACKEND_URL}/api/positions"
        positions_response = requests.get(positions_url, timeout=10)
        positions_response.raise_for_status()
        positions = positions_response.json()
        
        # Test 1: equity vs portfolio_value (should match)
        equity = account_data.get("equity")
        portfolio_value = account_data.get("portfolio_value")
        
        if equity and portfolio_value:
            diff = abs(equity - portfolio_value)
            if diff > 0.01:
                print_result("Equity vs Portfolio Value", False,
                            f"Equity (${equity:.2f}) and portfolio_value (${portfolio_value:.2f}) differ by ${diff:.2f}")
                return False
            else:
                print_result("Equity vs Portfolio Value", True,
                            f"Match: ${equity:.2f}")
        else:
            print_result("Equity vs Portfolio Value", True,
                        "One or both fields missing (acceptable)")
        
        # Test 2: long_market_value vs sum of positions
        long_market_value = account_data.get("long_market_value", 0)
        short_market_value = account_data.get("short_market_value", 0)
        
        if long_market_value > 0 and positions:
            # Calculate sum of all position market values (absolute values)
            calculated_long_value = sum(abs(p.get("market_value", 0)) for p in positions if p.get("market_value"))
            diff = abs(long_market_value - calculated_long_value)
            
            if diff > 1.0:  # Allow $1 difference for rounding/timing
                print_result("Long Market Value vs Positions", False,
                            f"long_market_value (${long_market_value:.2f}) doesn't match sum of positions "
                            f"(${calculated_long_value:.2f}), diff: ${diff:.2f}")
                return False
            else:
                print_result("Long Market Value vs Positions", True,
                            f"Match: ${long_market_value:.2f} (calculated: ${calculated_long_value:.2f}, diff: ${diff:.2f})")
        else:
            print_result("Long Market Value vs Positions", True,
                        "No positions or long_market_value is zero")
        
        # Test 3: equity calculation formula
        # equity = cash + long_market_value - short_market_value + non_tradable_assets + unsettled_funds
        cash = account_data.get("cash", 0)
        non_tradable_assets = account_data.get("non_tradable_assets", 0)
        unsettled_funds = account_data.get("unsettled_funds", 0)
        
        calculated_equity = (
            cash 
            + long_market_value 
            - short_market_value 
            + non_tradable_assets 
            + unsettled_funds
        )
        
        if equity:
            diff = abs(equity - calculated_equity)
            if diff > 1.0:  # Allow $1 difference for other factors
                print_result("Equity Formula Validation", False,
                            f"Equity (${equity:.2f}) doesn't match calculated value (${calculated_equity:.2f}), "
                            f"diff: ${diff:.2f}")
                print(f"  Components: cash=${cash:.2f}, long=${long_market_value:.2f}, "
                      f"short=${short_market_value:.2f}, non_tradable=${non_tradable_assets:.2f}, "
                      f"unsettled=${unsettled_funds:.2f}")
                return False
            else:
                print_result("Equity Formula Validation", True,
                            f"Equity matches formula: ${equity:.2f} (calculated: ${calculated_equity:.2f})")
        else:
            print_result("Equity Formula Validation", True,
                        "Equity field missing (cannot validate)")
        
        # Test 4: Verify we're using equity (not portfolio_value) as primary
        if equity:
            print_result("Using Equity as Primary", True,
                        f"Equity field available: ${equity:.2f}")
        else:
            print_result("Using Equity as Primary", False,
                        "Equity field missing - should use equity as primary")
            return False
        
        return True
        
    except Exception as e:
        print_result("Account Summary Calculations", False, f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("  PORTFOLIO HISTORY API TEST SUITE")
    print("=" * 80)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Paper Trading: {settings.use_paper_trading}")
    
    results = []
    
    # Test 1: Raw portfolio history
    results.append(("Raw Portfolio History", test_portfolio_history_raw()))
    
    # Test 2: All P/L periods
    results.append(("All P/L Periods", test_all_periods()))
    
    # Test 3: Chart data
    results.append(("Chart Data", test_portfolio_chart_data()))
    
    # Test 4: Today's P/L validation
    results.append(("Today's P/L Validation", test_today_pl_vs_account()))
    
    # Test 5: Account summary calculations
    results.append(("Account Summary Calculations", test_account_summary_calculations()))
    
    # Final summary
    print_section("FINAL SUMMARY")
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

