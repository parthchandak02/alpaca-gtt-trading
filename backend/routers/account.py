"""Account, positions, and market clock routes."""

import asyncio
import logging

from datetime import datetime, timedelta

from core.dependencies import AlpacaClientDep
from fastapi import APIRouter, HTTPException, Query
from rate_limiter import rate_limit_alpaca_call
from schemas import AccountResponse, PositionResponse, PortfolioHistoryResponse, PortfolioPLSummary
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["account"])

# Timeout for Alpaca API calls (25 seconds - fail before global 29s timeout)
ALPACA_API_TIMEOUT = 25.0


def safe_portfolio_pl_summary(**kwargs) -> PortfolioPLSummary:
    """Create PortfolioPLSummary ensuring NO None values can get through."""
    # Force all numeric fields to be 0.0 if None or missing - explicitly check for None
    def safe_float(v):
        """Convert value to float, defaulting to 0.0 if None or invalid."""
        if v is None:
            return 0.0
        try:
            result = float(v)
            # Handle NaN
            if result != result:  # NaN check
                return 0.0
            return result
        except (TypeError, ValueError):
            return 0.0
    
    # Log input to debug
    logger.debug(f"[safe_portfolio_pl_summary] Input kwargs: {kwargs}")
    
    safe_kwargs = {
        "period": kwargs.get("period", "unknown"),
        "profit_loss_dollars": safe_float(kwargs.get("profit_loss_dollars")),
        "profit_loss_percent": safe_float(kwargs.get("profit_loss_percent")),
        "equity": safe_float(kwargs.get("equity")),
        "base_value": safe_float(kwargs.get("base_value")),
        "base_value_asof": kwargs.get("base_value_asof"),
        "data_points": int(kwargs.get("data_points") or 0),
    }
    
    # Final safety check - ensure no None values (double-check)
    for key in ["profit_loss_dollars", "profit_loss_percent", "equity", "base_value"]:
        if safe_kwargs[key] is None:
            logger.warning(f"[safe_portfolio_pl_summary] Found None for {key}, converting to 0.0")
            safe_kwargs[key] = 0.0
    
    logger.debug(f"[safe_portfolio_pl_summary] Safe kwargs: {safe_kwargs}")
    
    # Use model_validate instead of constructor to ensure BeforeValidator runs
    # This is more reliable for Annotated types with BeforeValidator
    try:
        return PortfolioPLSummary.model_validate(safe_kwargs)
    except Exception as e:
        logger.error(f"[safe_portfolio_pl_summary] Error creating PortfolioPLSummary with model_validate: {e}, kwargs: {safe_kwargs}", exc_info=True)
        # Last resort - create with all defaults, ensuring no None values
        # Use model_validate to ensure BeforeValidator runs
        try:
            return PortfolioPLSummary.model_validate({
                "period": safe_kwargs.get("period", "unknown"),
                "profit_loss_dollars": 0.0,
                "profit_loss_percent": 0.0,
                "equity": 0.0,
                "base_value": 0.0,
                "base_value_asof": safe_kwargs.get("base_value_asof"),
                "data_points": safe_kwargs.get("data_points", 0),
            })
        except Exception as e2:
            logger.error(f"[safe_portfolio_pl_summary] Even model_validate failed: {e2}", exc_info=True)
            # Absolute last resort - return a minimal valid object
            # This should never happen if BeforeValidator is working
            raise RuntimeError(f"Failed to create PortfolioPLSummary even with defaults: {e2}") from e


@router.get("/account", response_model=AccountResponse)
async def get_account(alpaca_client: AlpacaClientDep):
    """Get account information.

    Uses run_in_threadpool to offload blocking Alpaca SDK call from event loop.
    Wrapped with timeout to prevent hanging requests through Cloudflare Tunnel.
    """
    try:
        # Rate limit before making API call
        await rate_limit_alpaca_call()

        # Use Starlette's run_in_threadpool (best practice for FastAPI)
        # This properly offloads the blocking SDK call from the async event loop
        account = await asyncio.wait_for(
            run_in_threadpool(alpaca_client.get_account), timeout=ALPACA_API_TIMEOUT
        )
        return account
    except TimeoutError:
        logger.error(
            f"Timeout fetching account: Alpaca API call exceeded {ALPACA_API_TIMEOUT}s"
        )
        raise HTTPException(
            status_code=504,
            detail=f"Account fetch timeout: Alpaca API did not respond within {ALPACA_API_TIMEOUT} seconds",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching account: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions", response_model=list[PositionResponse])
async def get_positions(alpaca_client: AlpacaClientDep):
    """Get current positions.

    Uses run_in_threadpool to offload blocking Alpaca SDK call from event loop.
    Wrapped with timeout to prevent hanging requests.
    """
    try:
        # Rate limit before making API call
        await rate_limit_alpaca_call()

        positions = await asyncio.wait_for(
            run_in_threadpool(alpaca_client.get_positions), timeout=ALPACA_API_TIMEOUT
        )
        return positions
    except TimeoutError:
        logger.error(
            f"Timeout fetching positions: Alpaca API call exceeded {ALPACA_API_TIMEOUT}s"
        )
        raise HTTPException(
            status_code=504,
            detail=f"Positions fetch timeout: Alpaca API did not respond within {ALPACA_API_TIMEOUT} seconds",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching positions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market-clock")
async def get_market_clock(alpaca_client: AlpacaClientDep):
    """Get market clock status.

    Uses run_in_threadpool to offload blocking Alpaca SDK call from event loop.
    Wrapped with timeout to prevent hanging requests.
    """
    try:
        # Rate limit before making API call
        await rate_limit_alpaca_call()

        clock = await asyncio.wait_for(
            run_in_threadpool(alpaca_client.get_market_clock),
            timeout=ALPACA_API_TIMEOUT,
        )
        return clock
    except TimeoutError:
        logger.error(
            f"Timeout fetching market clock: Alpaca API call exceeded {ALPACA_API_TIMEOUT}s"
        )
        raise HTTPException(
            status_code=504,
            detail=f"Market clock fetch timeout: Alpaca API did not respond within {ALPACA_API_TIMEOUT} seconds",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching market clock: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolio-history", response_model=PortfolioHistoryResponse)
async def get_portfolio_history(
    period: str | None = Query(None, description="Duration: 1D, 1W, 1M, 1A (day/week/month/year)"),
    timeframe: str | None = Query(None, description="Resolution: 1Min, 5Min, 15Min, 1H, 1D"),
    start: str | None = Query(None, description="Start timestamp (RFC3339)"),
    end: str | None = Query(None, description="End timestamp (RFC3339)"),
    intraday_reporting: str = Query("market_hours", description="market_hours, extended_hours, or continuous"),
    pnl_reset: str = Query("per_day", description="per_day or no_reset"),
    alpaca_client: AlpacaClientDep = ...,
):
    """Get portfolio history (equity and P/L over time).
    
    Returns timeseries data about equity and profit/loss of the account.
    Only two of start, end, and period can be specified at the same time.
    """
    try:
        # Rate limit before making API call
        await rate_limit_alpaca_call()
        
        history = await asyncio.wait_for(
            run_in_threadpool(
                alpaca_client.get_portfolio_history,
                period,
                timeframe,
                start,
                end,
                intraday_reporting,
                pnl_reset,
            ),
            timeout=ALPACA_API_TIMEOUT,
        )
        return history
    except TimeoutError:
        logger.error(
            f"Timeout fetching portfolio history: Alpaca API call exceeded {ALPACA_API_TIMEOUT}s"
        )
        raise HTTPException(
            status_code=504,
            detail=f"Portfolio history fetch timeout: Alpaca API did not respond within {ALPACA_API_TIMEOUT} seconds",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching portfolio history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolio-pl")
async def get_portfolio_pl(
    period: str = Query(..., description="Period: today, weekly, monthly, yearly, all_time"),
    alpaca_client: AlpacaClientDep = ...,
):
    """Get portfolio P/L summary for a specific period.
    
    Returns a dict (not using response_model) to avoid FastAPI validation issues with None values.
    """
    try:
        result = await _get_portfolio_pl_impl(period, alpaca_client)
        # Convert Pydantic model to dict and ensure no None values in numeric fields
        if result is None:
            logger.error(f"[get_portfolio_pl] Result is None for {period}")
            result_dict = {
                "period": period,
                "profit_loss_dollars": 0.0,
                "profit_loss_percent": 0.0,
                "equity": 0.0,
                "base_value": 0.0,
                "base_value_asof": None,
                "data_points": 0,
            }
        else:
            # Use model_dump to get dict, then sanitize any None values
            result_dict = result.model_dump()
            # Final sanitization - ensure no None values in numeric fields
            for key in ["profit_loss_dollars", "profit_loss_percent", "equity", "base_value"]:
                if result_dict.get(key) is None:
                    logger.warning(f"[get_portfolio_pl] Found None for {key} in result_dict, converting to 0.0")
                    result_dict[key] = 0.0
        
        return result_dict
    except Exception as e:
        logger.error(f"[get_portfolio_pl] Outer exception handler caught: {e}", exc_info=True)
        # If it's a validation error, return empty summary instead of 500
        if "validation" in str(e).lower() or "float_type" in str(e):
            logger.warning(f"[get_portfolio_pl] Validation error for {period}, returning empty summary")
            return {
                "period": period,
                "profit_loss_dollars": 0.0,
                "profit_loss_percent": 0.0,
                "equity": 0.0,
                "base_value": 0.0,
                "base_value_asof": None,
                "data_points": 0,
            }
        raise


async def _get_portfolio_pl_impl(
    period: str,
    alpaca_client: AlpacaClientDep,
):
    """Internal implementation of get_portfolio_pl.
    
    For "today": Uses account data (equity - last_equity) for faster response.
    For other periods: Uses portfolio history API:
    - weekly: Last 7 days (1D timeframe)
    - monthly: Last 30 days (1D timeframe)
    - yearly: Last 1 year (1D timeframe)
    - all_time: All available data (1D timeframe)
    """
    try:
        # Rate limit before making API call
        await rate_limit_alpaca_call()
        
        # For "today", use account data (faster, no API call needed)
        if period == "today":
            account = await asyncio.wait_for(
                run_in_threadpool(alpaca_client.get_account), timeout=ALPACA_API_TIMEOUT
            )
            
            equity = account.get("equity", 0.0)
            last_equity = account.get("last_equity")
            
            if last_equity is None or last_equity == 0:
                # No previous equity data, return zero P/L
                return safe_portfolio_pl_summary(
                    period="today",
                    profit_loss_dollars=0.0,
                    profit_loss_percent=0.0,
                    equity=equity or 0.0,
                    base_value=equity or 0.0,
                    base_value_asof=None,
                    data_points=1,
                )
            
            # Calculate today's P/L
            pl_dollars = equity - last_equity
            pl_percent = ((equity - last_equity) / last_equity * 100) if last_equity > 0 else 0.0
            
            return safe_portfolio_pl_summary(
                period="today",
                profit_loss_dollars=pl_dollars or 0.0,
                profit_loss_percent=pl_percent or 0.0,
                equity=equity or 0.0,
                base_value=last_equity or 0.0,
                base_value_asof=None,
                data_points=1,
            )
        
        # Map period to Alpaca API parameters
        period_map = {
            "weekly": ("7D", "1D"),
            "monthly": ("30D", "1D"),
            "yearly": ("1A", "1D"),  # 1A = 1 year
            "all_time": (None, "1D"),  # No period limit, will get all data
        }
        
        if period not in period_map:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid period: {period}. Must be one of: today, weekly, monthly, yearly, all_time",
            )
        
        alpaca_period, timeframe = period_map[period]
        
        # For all_time, we need to use start/end instead of period
        # Alpaca API: when period is None and start is provided, it returns data from start to now
        # Use account creation date approximation (10 years ago should cover most accounts)
        # If account is older, Alpaca will return data from account creation anyway
        if period == "all_time":
            # Try with start date 10 years ago (Alpaca will return data from account creation if older)
            # Format: RFC3339 format (YYYY-MM-DDTHH:MM:SSZ)
            start_date_10y = (datetime.now() - timedelta(days=3650)).isoformat() + "Z"
            try:
                history = await asyncio.wait_for(
                    run_in_threadpool(
                        alpaca_client.get_portfolio_history,
                        None,  # period
                        timeframe,
                        start_date_10y,  # start
                        None,  # end (defaults to now)
                        "market_hours",
                        "per_day",
                    ),
                    timeout=ALPACA_API_TIMEOUT,
                )
            except Exception as e:
                # If 10 years fails, try with 5 years as fallback
                logger.warning(f"Failed to fetch all_time with start date {start_date_10y}, trying 5 years: {e}", exc_info=True)
                start_date_5y = (datetime.now() - timedelta(days=1825)).isoformat() + "Z"
                try:
                    history = await asyncio.wait_for(
                        run_in_threadpool(
                            alpaca_client.get_portfolio_history,
                            None,  # period
                            timeframe,
                            start_date_5y,  # start
                            None,  # end (defaults to now)
                            "market_hours",
                            "per_day",
                        ),
                        timeout=ALPACA_API_TIMEOUT,
                    )
                except Exception as e2:
                    # If 5 years fails, try with 2 years as final fallback
                    logger.warning(f"Failed to fetch all_time with start date {start_date_5y}, trying 2 years: {e2}", exc_info=True)
                    start_date_2y = (datetime.now() - timedelta(days=730)).isoformat() + "Z"
                    try:
                        history = await asyncio.wait_for(
                            run_in_threadpool(
                                alpaca_client.get_portfolio_history,
                                None,  # period
                                timeframe,
                                start_date_2y,  # start
                                None,  # end (defaults to now)
                                "market_hours",
                                "per_day",
                            ),
                            timeout=ALPACA_API_TIMEOUT,
                        )
                    except Exception as e3:
                        # If all attempts fail, return empty data with defaults instead of raising error
                        logger.error(f"Failed to fetch all_time portfolio history (all attempts failed). Last error: {e3}", exc_info=True)
                        # Return empty summary instead of raising - this prevents 500 errors
                        return safe_portfolio_pl_summary(
                            period=period,
                            profit_loss_dollars=0.0,
                            profit_loss_percent=0.0,
                            equity=0.0,
                            base_value=0.0,
                            base_value_asof=None,
                            data_points=0,
                        )
        else:
            history = await asyncio.wait_for(
                run_in_threadpool(
                    alpaca_client.get_portfolio_history,
                    alpaca_period,
                    timeframe,
                    None,  # start
                    None,  # end
                    "market_hours",
                    "per_day",
                ),
                timeout=ALPACA_API_TIMEOUT,
            )
        
        # Validate history response
        if history is None:
            logger.error(f"Portfolio history response is None for period {period}")
            return safe_portfolio_pl_summary(
                    period=period,
                    profit_loss_dollars=0.0,
                    profit_loss_percent=0.0,
                    equity=0.0,
                    base_value=0.0,
                    base_value_asof=None,
                    data_points=0,
                )
        
        # Extract latest values for P/L summary
        equity_array = history.get("equity", [])
        if not equity_array or len(equity_array) == 0:
            # No data available
            base_value = history.get("base_value")
            base_value = float(base_value) if base_value is not None else 0.0
            return safe_portfolio_pl_summary(
                period=period,
                profit_loss_dollars=0.0,
                profit_loss_percent=0.0,
                equity=0.0,
                base_value=base_value or 0.0,
                base_value_asof=history.get("base_value_asof"),
                data_points=0,
            )
        
        # Get latest equity and P/L values
        # Filter out None values from arrays (Alpaca may return None in arrays)
        # Note: Keep 0.0 values, only filter None
        equity_array_clean = [v for v in equity_array if v is not None]
        profit_loss_array = [v for v in history.get("profit_loss", []) if v is not None]
        profit_loss_pct_array = [v for v in history.get("profit_loss_pct", []) if v is not None]
        
        # Use original array length for data_points, but use cleaned array for latest value
        if not equity_array_clean:
            # No valid equity data (all None)
            base_value = history.get("base_value")
            base_value = float(base_value) if base_value is not None else 0.0
            return safe_portfolio_pl_summary(
                period=period,
                profit_loss_dollars=0.0,
                profit_loss_percent=0.0,
                equity=0.0,
                base_value=base_value or 0.0,
                base_value_asof=history.get("base_value_asof") if history.get("base_value_asof") != "0000-00-00" else None,
                data_points=len(equity_array),
            )
        
        # Get latest values (after filtering None)
        # CRITICAL: Filter None values BEFORE accessing [-1], as Alpaca can return None in arrays
        latest_equity = equity_array_clean[-1] if equity_array_clean else 0.0
        latest_pl = profit_loss_array[-1] if profit_loss_array else 0.0
        
        # Handle case where latest values might still be None (shouldn't happen after filtering, but be safe)
        if latest_equity is None:
            latest_equity = 0.0
        if latest_pl is None:
            latest_pl = 0.0
        
        # Handle base_value - ensure it's always a float, never None
        # According to Alpaca API docs: base_value can be None if portfolio has no value
        base_value_raw = history.get("base_value")
        if base_value_raw is None:
            # If base_value is None from API, use first equity value as base
            if equity_array_clean and len(equity_array_clean) > 0:
                base_value = float(equity_array_clean[0])
            else:
                # No equity data, use latest equity as base (or 0.0)
                # Handle case where latest_equity might be 0.0 (falsy but valid)
                if latest_equity is not None:
                    base_value = float(latest_equity)
                else:
                    base_value = 0.0
        else:
            base_value = float(base_value_raw)
        
        # Ensure base_value is never None or invalid
        if base_value is None or (isinstance(base_value, float) and (base_value != base_value)):  # Check for NaN
            base_value = 0.0
        
        # Calculate P/L percentage
        # Alpaca formula: pnl_pct = equity/base_value - 1
        # CRITICAL: profit_loss_pct_array may contain None values, so filter them first
        latest_pl_pct = 0.0  # Initialize
        if profit_loss_pct_array and len(profit_loss_pct_array) > 0:
            # Filter out None values and get the last valid value
            valid_pct_values = [v for v in profit_loss_pct_array if v is not None]
            if valid_pct_values:
                # Use last valid API value
                latest_pl_pct = float(valid_pct_values[-1])
            else:
                # All values were None, calculate from equity and base_value
                if base_value > 0:
                    latest_pl_pct = ((latest_equity / base_value) - 1) * 100
                else:
                    latest_pl_pct = 0.0
        else:
            # No array or empty array, calculate P/L percentage from equity and base_value
            if base_value > 0:
                latest_pl_pct = ((latest_equity / base_value) - 1) * 100
            else:
                latest_pl_pct = 0.0
        
        # Final safety check - ensure latest_pl_pct is never None
        if latest_pl_pct is None:
            latest_pl_pct = 0.0
        
        # CRITICAL: Ensure base_value is never None (double-check)
        if base_value is None:
            logger.warning(f"[get_portfolio_pl] base_value is None for period {period}, setting to 0.0")
            base_value = 0.0
        
        # Handle invalid base_value_asof dates
        base_value_asof = history.get("base_value_asof")
        if base_value_asof == "0000-00-00" or base_value_asof is None:
            base_value_asof = None
        
        # Log before final sanitization
        logger.debug(f"[get_portfolio_pl] Before sanitization - latest_pl_pct={latest_pl_pct} (type: {type(latest_pl_pct)}), base_value={base_value} (type: {type(base_value)})")
        
        # SIMPLIFIED: Final sanitization - convert to float, ensuring NO None values
        # Explicitly convert and validate ALL values before passing to Pydantic
        # Use or 0.0 to handle any edge cases where values might be None
        try:
            profit_loss_dollars_final = float(latest_pl) if latest_pl is not None else 0.0
        except (TypeError, ValueError):
            profit_loss_dollars_final = 0.0
            
        try:
            profit_loss_percent_final = float(latest_pl_pct) if latest_pl_pct is not None else 0.0
        except (TypeError, ValueError):
            profit_loss_percent_final = 0.0
            
        try:
            equity_final = float(latest_equity) if latest_equity is not None else 0.0
        except (TypeError, ValueError):
            equity_final = 0.0
            
        try:
            base_value_final = float(base_value) if base_value is not None else 0.0
        except (TypeError, ValueError):
            base_value_final = 0.0
        
        # Final safety check - ensure no None values slip through (but preserve 0.0 values)
        if profit_loss_dollars_final is None:
            profit_loss_dollars_final = 0.0
        if profit_loss_percent_final is None:
            profit_loss_percent_final = 0.0
        if equity_final is None:
            equity_final = 0.0
        if base_value_final is None:
            base_value_final = 0.0
        
        # Log values before return to debug - check for None explicitly
        logger.info(f"[DEBUG] PortfolioPLSummary values for {period}: pl={profit_loss_dollars_final} (type: {type(profit_loss_dollars_final)}), pl_pct={profit_loss_percent_final} (type: {type(profit_loss_percent_final)}), equity={equity_final} (type: {type(equity_final)}), base={base_value_final} (type: {type(base_value_final)})")
        
        # CRITICAL: Ensure NO None values can possibly get through - use dict construction
        summary_data = {
            "period": period,
            "profit_loss_dollars": profit_loss_dollars_final if profit_loss_dollars_final is not None else 0.0,
            "profit_loss_percent": profit_loss_percent_final if profit_loss_percent_final is not None else 0.0,
            "equity": equity_final if equity_final is not None else 0.0,
            "base_value": base_value_final if base_value_final is not None else 0.0,
            "base_value_asof": base_value_asof,
            "data_points": len(equity_array),
        }
        
        # Log the dict to verify
        logger.info(f"[DEBUG] PortfolioPLSummary dict: {summary_data}")
        
        return safe_portfolio_pl_summary(**summary_data)
    except TimeoutError:
        logger.error(
            f"Timeout fetching portfolio P/L ({period}): Alpaca API call exceeded {ALPACA_API_TIMEOUT}s"
        )
        raise HTTPException(
            status_code=504,
            detail=f"Portfolio P/L fetch timeout: Alpaca API did not respond within {ALPACA_API_TIMEOUT} seconds",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching portfolio P/L for period '{period}': {e}", exc_info=True)
        # Provide more helpful error message for all_time period
        if period == "all_time":
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch all-time portfolio history. This may be due to account age or API limitations. Error: {str(e)}"
            )
        raise HTTPException(status_code=500, detail=f"Failed to fetch portfolio P/L: {str(e)}")
