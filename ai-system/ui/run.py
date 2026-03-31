#!/usr/bin/env python3
"""Launch the AIL Pipeline Dashboard."""

import os
import sys
import uvicorn

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if __name__ == "__main__":
    host = os.environ.get("AIL_UI_HOST", "0.0.0.0")
    port = int(os.environ.get("AIL_UI_PORT", "8080"))

    print(f"\n  AIL Pipeline Dashboard")
    print(f"  http://{host}:{port}\n")

    uvicorn.run(
        "ui.api:app",
        host=host,
        port=port,
        reload=True,
        log_level="info",
    )
