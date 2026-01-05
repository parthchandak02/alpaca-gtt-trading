# Alpaca GTT Order Tracker

GTT (Good-Till-Triggered) order management with real-time price monitoring and automated order execution via Alpaca API.

## Quick Start

```bash
# Start everything (backend + frontend)
./scripts/10-run-all.sh
```

- Backend: http://localhost:8000
- Frontend: http://localhost:3000

## Configuration

Create `.env` in project root (see `example.env`):

```bash
# Required - Alpaca API
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
ALPACA_PAPER=true  # false for live trading

# Optional - WhatsApp notifications
WHATSAPP_ENABLED=false
WHATSAPP_PHONE_NUMBER=14155551234
WHATSAPP_GROUP_ID=123456789@g.us  # Optional: send to group instead
WAHA_API_URL=http://localhost:3001
WAHA_API_KEY=your_waha_key
```

## Features

- **GTT Ladder Orders** - Create cascading buy orders that trigger as price drops
- **Real-time Prices** - WebSocket price updates with HTTP polling fallback
- **Automated Execution** - Orders auto-submit when price drops below trigger
- **Fractional Trading** - Support for crypto and fractional stock quantities
- **CSV Bulk Upload** - Import multiple orders via CSV templates
- **Price Charts** - Interactive charts with trigger level visualization
- **Daily Summaries** - WhatsApp notifications for order fills, failures, and daily reports
- **Separate Databases** - Paper and live trading use isolated databases

## Scripts

Numbered by category (1x=Dev, 2x=Deploy, 3x=Maintenance, 4x=Testing, 5x=WhatsApp):

**Development (1x)**
- `10-run-all.sh` - Start backend + frontend
- `11-run-backend.sh` - Backend only
- `12-run-frontend.sh` - Frontend only

**Deployment (2x)**
- `20-deploy-frontend.sh` - Deploy to Cloudflare Pages
- `21-setup-tunnel.sh` - Setup Cloudflare tunnel
- `22-start-tunnel.sh` - Start tunnel
- `24-deploy.sh` - Git push + Cloudflare deploy

**Maintenance (3x)**
- `30-cleanup-restart.sh` - Full reset
- `32-fix-code-quality.sh` - Auto-fix linting (Ruff)
- `33-check-code-quality.sh` - Check code quality
- `36-reset-paper-db.sh` - Reset paper trading DB
- `37-verify-gtt-readiness.sh` - Pre-market check

**Testing (4x)**
- `40-test-e2e-flow.py` - End-to-end flow
- `44-test-verify-gtt-triggers.py` - Trigger logic verification
- `47-analyze-gtt-orders.py` - Order analysis
- `48-check-backend-health.py` - API health check
- `49-run-tests.sh` - Test suite

**WhatsApp (5x)**
- `50-setup-waha.sh` - Setup WAHA container
- `51-setup-waha-session.sh` - Setup WhatsApp session
- `52-get-waha-qr.sh` - Get QR code for linking
- `54-test-whatsapp.py` - Test notifications
- `55-trigger-daily-summary.py` - Manual daily summary

## Production

```bash
# Local (PM2)
pm2 start ecosystem.config.js
pm2 logs

# Deploy frontend
./scripts/20-deploy-frontend.sh
```

## WhatsApp Notifications

Optional notifications for order fills, failures, and daily summaries.

```bash
# 1. Start WAHA (shared instance at ~/Documents/waha)
./scripts/50-setup-waha.sh

# 2. Add to .env (get API key from script output)
WHATSAPP_ENABLED=true
WHATSAPP_PHONE_NUMBER=14155551234
WHATSAPP_GROUP_ID=123456789@g.us  # Optional: group notifications
WAHA_API_URL=http://localhost:3001
WAHA_API_KEY=your_key_here

# 3. Setup session (scan QR with WhatsApp)
./scripts/51-setup-waha-session.sh

# 4. Test
backend/.venv/bin/python scripts/54-test-whatsapp.py

# Manual daily summary (or use --dry-run to preview)
backend/.venv/bin/python scripts/55-trigger-daily-summary.py --dry-run
```

WAHA is managed at `~/Documents/waha`. Use `./manage.sh start|stop|status` there.

## Order Requirements

| Requirement | Value | Notes |
|-------------|-------|-------|
| Min Order Value | $1.00 | quantity x price >= $1 |
| Min Quantity | 0.01 | Fractional orders |
| Safety Drop (Crypto) | 50% | Allows volatile drops |
| Safety Drop (Stocks) | 20% | Protects against bad data |

**Order Expiration**: Corporate actions (splits, mergers) expire all remaining ladder levels.

## Architecture

```
alpaca-trader/
├── backend/           # Python + FastAPI + SQLite
│   ├── core/          # Services (prices, websocket, whatsapp)
│   ├── routers/       # API endpoints
│   └── gtt_service.py # GTT order logic
├── frontend/          # Next.js + React + TypeScript
│   ├── app/           # Pages (login, gtt)
│   ├── components/    # UI components
│   ├── hooks/         # React hooks
│   └── lib/           # Utilities, types, theme
└── scripts/           # Automation scripts
```

**Real-time Updates**:
- WebSocket for price streaming
- SSE (Server-Sent Events) for order status updates
- Heartbeat every 15s (Cloudflare timeout protection)

## Tech Stack

- **Backend**: Python 3.11+ / FastAPI / SQLAlchemy / SQLite
- **Frontend**: Next.js 15 / React 19 / TypeScript / Tailwind CSS
- **Real-time**: Alpaca WebSocket / SSE
- **Deployment**: Cloudflare Pages (frontend) + Tunnel (backend)
- **Notifications**: WAHA (WhatsApp HTTP API)

## Troubleshooting

```bash
./scripts/30-cleanup-restart.sh     # Full reset
./scripts/31-fix-db-permissions.sh  # Fix DB permissions
pm2 restart alpaca-backend          # Restart backend
docker logs waha                    # WAHA logs
```
