"""Version information router."""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["version"])

# Path to version.json file
VERSION_FILE = Path(__file__).parent.parent / "version.json"


@router.get("/version")
async def get_version():
    """
    Get backend version information.

    Returns build version, timestamp, and git information.
    """
    try:
        if VERSION_FILE.exists():
            with open(VERSION_FILE) as f:
                version_data = json.load(f)
                return version_data
        else:
            # Return default version if file doesn't exist
            logger.warning(f"Version file not found: {VERSION_FILE}")
            return {
                "version": "dev",
                "buildTime": "unknown",
                "buildTimeReadable": "Development Mode",
                "gitCommit": "unknown",
                "gitCommitShort": "dev",
                "gitBranch": "unknown",
            }
    except Exception as e:
        logger.error(f"Error reading version file: {e}")
        raise HTTPException(status_code=500, detail=f"Error reading version: {e!s}")
