# Alpaca GTT Order Tracker

GTT order management with real-time price monitoring and automated order execution.

## Quick Start

```bash
./scripts/10-run-all.sh  # Starts backend (8000) + frontend (3000)
```

## Configuration

Single `.env` file in project root (see `.env.example`).

## Code Quality

Uses **Ruff** (linter) and **Vulture** (dead code detector).

```bash
# Check for issues
bash scripts/33-check-code-quality.sh

# Auto-fix issues (linting + formatting)
bash scripts/32-fix-code-quality.sh
```

**Tools:**
- **Ruff**: Finds unused imports, variables, code style issues, common bugs (auto-fixes 983+ issues)
- **Vulture**: Finds dead/unused code (functions, classes, imports)

## Scripts

Scripts are organized by category with numbered prefixes (first digit = category, second digit = script number):

**1x - Development**
- `10-run-all.sh` - Start backend + frontend together
- `11-run-backend.sh` - Start backend only
- `12-run-frontend.sh` - Start frontend only

**2x - Deployment**
- `20-deploy-frontend.sh` - Deploy frontend to Cloudflare Pages
- `21-setup-tunnel.sh` - Setup Cloudflare tunnel configuration
- `22-start-tunnel.sh` - Start Cloudflare tunnel
- `23-check-config.sh` - Verify Cloudflare configuration
- `24-deploy.sh` - Combined deployment (Git push + Cloudflare Pages)

**3x - Maintenance**
- `30-cleanup-restart.sh` - Cleanup and restart services
- `31-fix-db-permissions.sh` - Fix database permissions
- `32-fix-code-quality.sh` - Auto-fix code quality issues
- `33-check-code-quality.sh` - Check code quality
- `34-generate-version.sh` - Generate version file
- `35-complete-setup.sh` - Complete setup checklist for production
- `36-reset-paper-db.sh` - Reset paper trading database
- `37-verify-gtt-readiness.sh` - Verify GTT system readiness for market open
- `38-reactivate-expired-orders.py` - Safely reactivate incorrectly expired GTT orders
- `39-check-expired-orders.py` - Check for expired GTT orders in database

**4x - Testing & Analysis**
- `40-test-e2e-flow.py` - End-to-end flow test
- `41-test-price-cache.py` - Price cache service test
- `42-test-gtt-order-status.py` - GTT order status test
- `43-test-alpaca-websocket.py` - Alpaca WebSocket test
- `44-test-verify-gtt-triggers.py` - Verify GTT trigger logic (diagnostic tool)
- `45-test-portfolio-history.py` - Portfolio history test
- `46-check-missed-triggers.py` - Check for missed triggers using historical data
- `47-analyze-gtt-orders.py` - Comprehensive order analysis (safety checks, balance issues)
- `48-check-backend-health.py` - Check backend API health
- `49-run-tests.sh` - Run automated test suite
- `55-trigger-daily-summary.py` - Manually trigger daily failed orders summary

**5x - WhatsApp Integration**
- `50-setup-waha.sh` - Setup WAHA Docker container
- `51-setup-waha-session.sh` - Setup WAHA session
- `52-get-waha-qr.sh` - Get QR code for WhatsApp linking
- `53-search-waha-groups.py` - Search WhatsApp groups
- `54-test-whatsapp.py` - WhatsApp notification test

## Production

```bash
# Local (PM2)
pm2 start ecosystem.config.js
pm2 logs

# Deploy Frontend
./scripts/20-deploy-frontend.sh

# Verify Config
./scripts/23-check-config.sh
```

## WhatsApp Notifications (Optional)

Get WhatsApp notifications when GTT orders fill, fail, or are cancelled.

```bash
# 1. Setup WAHA Docker container
./scripts/50-setup-waha.sh

# 2. Add to .env:
# WHATSAPP_ENABLED=true
# WHATSAPP_PHONE_NUMBER=14258983101  # Your phone (digits only, no +)
# WAHA_API_URL=http://localhost:3001
# WAHA_API_KEY=<get from docker logs waha | grep WAHA_API_KEY>
# WAHA_SESSION_NAME=default

# 3. Open Swagger UI: http://localhost:3001/
#    - Click "Authorize" (top right)
#    - Enter API key from step 2
#    - Create session: POST /api/sessions {"name": "default"}
#    - Get QR code: GET /api/{session}/auth/qr
#    - Scan QR code with WhatsApp

# 4. Test it
backend/.venv/bin/python scripts/54-test-whatsapp.py

# Search groups
backend/.venv/bin/python scripts/53-search-waha-groups.py "USA"
```

**Notifications are sent automatically for:**
- ✅ ORDER_FILLED - When GTT orders are executed
- ❌ ORDER_FAILED - When orders fail
- 🚫 ORDER_CANCELLED - When orders are cancelled
- ⚠️ CORPORATE_ACTION_EXPIRED - When orders expire due to corporate actions

## Troubleshooting

```bash
./scripts/30-cleanup-restart.sh        # Full reset
./scripts/31-fix-db-permissions.sh    # Fix DB permissions
pm2 restart alpaca-backend              # Restart backend
```

## Critical Architecture Patterns

### 1. Real-Time Connections (SSE) & Cloudflare
- **Backend:** Send heartbeat every **15 seconds** (Cloudflare closes idle connections after ~100s)
- **Frontend:** Use `useRef` for callbacks in `useEffect` to prevent infinite reconnection loops

### 2. API Rate Limiting
- Use **Debounce** hook (`useDebounce`) for search inputs (wait 500ms after typing stops)

## Order Requirements

**Minimum Order Value**: $1.00 USD (all orders must meet this)
- Formula: `quantity × price ≥ $1.00`
- Orders below minimum are rejected at creation

**Minimum Quantity**: 0.01 (for fractional orders)
- Applies to crypto and fractional stocks
- Non-fractionable assets require whole numbers

**Safety Check**: Prevents orders when price drops too dramatically
- Crypto: 50% drop threshold (allows volatile market drops)
- Stocks: 20% drop threshold (protects against symbol mismatches)

**Order Expiration**: Orders expire due to corporate actions (splits, mergers, delistings)
- When an order expires, **all remaining ladder levels are cancelled** (entire GTT order is marked EXPIRED)
- Expired orders are displayed in the frontend with red "EXPIRED" badges
- Remaining pending order details will **not** be processed after expiration

## Features

- GTT order management with ladder orders
- Real-time price updates via WebSocket with HTTP polling fallback
- Automated order triggering when prices drop below trigger points
- CSV bulk upload
- Interactive price charts with trigger levels
- Fractional trading validation
- Separate databases for paper/live trading
- WhatsApp notifications (optional) - Get notified when orders fill/fail

## Tech Stack

- **Backend**: Python + FastAPI + SQLite
- **Frontend**: Next.js 16 + React 19 + TypeScript
- **Real-time**: WebSocket (prices) + SSE (order events)
- **Deployment**: Cloudflare Pages (frontend) + Cloudflare Tunnel (backend)
