"""CSV template and utility routes."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

router = APIRouter(prefix="/api", tags=["csv"])

# Get the project root directory (two levels up from routers)
# Path(__file__) = backend/routers/csv.py
# Path(__file__).parent = backend/routers/
# Path(__file__).parent.parent = backend/
# Path(__file__).parent.parent.parent = project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
STOCKS_TEMPLATE_FILE = PROJECT_ROOT / "templates" / "template_stocks.csv"
CRYPTO_TEMPLATE_FILE = PROJECT_ROOT / "templates" / "template_crypto.csv"


@router.get("/csv-template")
async def get_csv_template():
    """Get CSV template for bulk upload (stocks) - legacy endpoint for backward compatibility."""
    return await get_stocks_template()


@router.get("/csv-template/stocks")
async def get_stocks_template():
    """Get CSV template for stocks bulk upload."""
    try:
        if not STOCKS_TEMPLATE_FILE.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Stocks template file not found at {STOCKS_TEMPLATE_FILE}",
            )

        # Read the template file
        with open(STOCKS_TEMPLATE_FILE, encoding="utf-8") as f:
            content = f.read()

        return Response(
            content=content,
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=gtt_template_stocks.csv"
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error reading stocks template file: {e!s}"
        )


@router.get("/csv-template/crypto")
async def get_crypto_template():
    """Get CSV template for crypto bulk upload."""
    try:
        if not CRYPTO_TEMPLATE_FILE.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Crypto template file not found at {CRYPTO_TEMPLATE_FILE}",
            )

        # Read the template file
        with open(CRYPTO_TEMPLATE_FILE, encoding="utf-8") as f:
            content = f.read()

        return Response(
            content=content,
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=gtt_template_crypto.csv"
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error reading crypto template file: {e!s}"
        )
