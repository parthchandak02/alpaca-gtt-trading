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

Create `.env` in project root:

```bash
# ========== TRADING MODE ==========
USE_PAPER_TRADING=true  # false for live trading

# ========== ALPACA API - PAPER ==========
ALPACA_PAPER_API_KEY=your_paper_key
ALPACA_PAPER_SECRET_KEY=your_paper_secret

# ========== ALPACA API - LIVE ==========
ALPACA_LIVE_API_KEY=your_live_key
ALPACA_LIVE_SECRET_KEY=your_live_secret

# ========== AUTHENTICATION ==========
UI_PASSWORD=your_ui_password
JWT_SECRET_KEY=your_jwt_secret  # Generate with: openssl rand -hex 32

# ========== SERVER ==========
HOST=0.0.0.0
PORT=8000
CORS_ORIGINS=http://localhost:3000,https://your-domain.com
NEXT_PUBLIC_API_URL=http://localhost:8000

# ========== OPTIONAL: WHATSAPP ==========
WHATSAPP_ENABLED=false
WHATSAPP_PHONE_NUMBER=14155551234  # Digits only, no +
WHATSAPP_GROUP_ID=123456789@g.us   # Optional: send to group
WAHA_API_URL=http://localhost:3001
WAHA_API_KEY=your_waha_key
WAHA_SESSION_NAME=default

# ========== OPTIONAL: CLOUDFLARE ==========
CLOUDFLARE_API_TOKEN=your_token
CLOUDFLARE_ACCOUNT_ID=your_account_id

# ========== OPTIONAL: DEBUG ==========
LOG_LEVEL=INFO
DEBUG=false
```

## Features

- **GTT Ladder Orders** - Create cascading buy orders that trigger as price drops
- **Real-time Prices** - WebSocket price updates with HTTP polling fallback
- **Automated Execution** - Orders auto-submit when price hits trigger level
- **Fractional Trading** - Support for crypto and fractional stock quantities
- **CSV Bulk Upload** - Import multiple orders via CSV templates
- **Price Charts** - Interactive charts with trigger level visualization
- **Daily Summaries** - WhatsApp notifications for order fills, failures, P/L reports
- **Separate Databases** - Paper and live trading use isolated databases
- **Order Linking** - Manually link existing Alpaca orders to GTT tracking

## Scripts

All scripts are in `/scripts/`, numbered by category:

### Development (1x)
| Script | Description |
|--------|-------------|
| `10-run-all.sh` | Start backend + frontend together |
| `11-run-backend.sh` | Start backend only |
| `12-run-frontend.sh` | Start frontend only |

### Deployment (2x)
| Script | Description |
|--------|-------------|
| `20-deploy-frontend.sh` | Deploy frontend to Cloudflare Pages |
| `21-setup-tunnel.sh` | Setup Cloudflare tunnel configuration |
| `22-start-tunnel.sh` | Start Cloudflare tunnel |
| `23-check-config.sh` | Verify Cloudflare configuration |
| `24-deploy.sh` | Git push + Cloudflare Pages deploy |

### Maintenance (3x)
| Script | Description |
|--------|-------------|
| `30-cleanup-restart.sh` | Full cleanup and restart services |
| `31-fix-db-permissions.sh` | Fix database file permissions |
| `32-fix-code-quality.sh` | Auto-fix linting issues (Ruff) |
| `33-check-code-quality.sh` | Check code quality without fixing |
| `34-generate-version.sh` | Generate version.json for deployments |
| `35-complete-setup.sh` | Production setup checklist |
| `36-reset-paper-db.sh` | Reset paper trading database |
| `37-verify-gtt-readiness.sh` | Pre-market readiness check |
| `38-reactivate-expired-orders.py` | Reactivate incorrectly expired orders |
| `39-check-expired-orders.py` | Check for expired orders in DB |

### Testing (4x)
| Script | Description |
|--------|-------------|
| `40-test-e2e-flow.py` | End-to-end order flow test |
| `41-test-price-cache.py` | Price cache service test |
| `42-test-gtt-order-status.py` | GTT order status test |
| `43-test-alpaca-websocket.py` | Alpaca WebSocket test |
| `44-test-verify-gtt-triggers.py` | Verify GTT trigger logic |
| `45-test-portfolio-history.py` | Portfolio history test |
| `46-check-missed-triggers.py` | Check for missed triggers |
| `47-analyze-gtt-orders.py` | Order analysis (safety, balance) |
| `48-check-backend-health.py` | Backend API health check |
| `49-run-tests.sh` | Run automated test suite |

### WhatsApp (5x)
| Script | Description |
|--------|-------------|
| `50-setup-waha.sh` | Setup WAHA Docker container |
| `51-setup-waha-session.sh` | Setup WhatsApp session |
| `52-get-waha-qr.sh` | Get QR code for WhatsApp linking |
| `53-search-waha-groups.py` | Search WhatsApp groups |
| `54-test-whatsapp.py` | Test WhatsApp notifications |
| `55-trigger-daily-summary.py` | Manually trigger daily summary |

## Production

```bash
# Start with PM2
pm2 start ecosystem.config.js
pm2 logs

# Deploy frontend to Cloudflare
./scripts/20-deploy-frontend.sh

# Check configuration
./scripts/23-check-config.sh
```

## WhatsApp Notifications

Optional notifications for order fills, failures, and daily summaries.

```bash
# 1. Start WAHA (shared instance at ~/Documents/waha)
./scripts/50-setup-waha.sh

# 2. Add to .env (API key shown in script output)
WHATSAPP_ENABLED=true
WHATSAPP_PHONE_NUMBER=14155551234
WHATSAPP_GROUP_ID=123456789@g.us  # Optional: group notifications
WAHA_API_URL=http://localhost:3001
WAHA_API_KEY=your_key_here

# 3. Setup session (scan QR code with WhatsApp)
./scripts/51-setup-waha-session.sh

# 4. Test notification
backend/.venv/bin/python scripts/54-test-whatsapp.py

# 5. Manual daily summary (use --dry-run to preview)
backend/.venv/bin/python scripts/55-trigger-daily-summary.py --dry-run
```

**WAHA Management** (at `~/Documents/waha`):
```bash
./manage.sh start|stop|restart|status
```

**Automatic Notifications:**
- ORDER_FILLED - When GTT orders execute
- ORDER_FAILED - When orders fail
- ORDER_CANCELLED - When orders are cancelled
- CORPORATE_ACTION_EXPIRED - When orders expire due to splits/mergers
- Daily Summary - Sent at market close (P/L, fills, pending orders)

## Order Requirements

| Requirement | Value | Notes |
|-------------|-------|-------|
| Min Order Value | $1.00 | quantity x price >= $1 |
| Min Quantity | 0.01 | Fractional orders |
| Safety Drop (Crypto) | 50% | Allows volatile market drops |
| Safety Drop (Stocks) | 20% | Protects against bad data/symbol mismatch |

**Order Expiration**: Corporate actions (splits, mergers, delistings) expire all remaining ladder levels. Expired orders show a red "EXPIRED" badge in the UI.

## Architecture

```
alpaca-trader/
├── backend/                 # Python + FastAPI + SQLite
│   ├── core/               # Core services
│   │   ├── background_tasks.py    # Price monitoring loop
│   │   ├── daily_summary_service.py  # Daily reports
│   │   ├── price_cache_service.py    # Price caching
│   │   ├── sse_manager.py           # Server-Sent Events
│   │   ├── websocket_manager.py     # WebSocket handling
│   │   └── whatsapp_service.py      # WAHA integration
│   ├── routers/            # API endpoints
│   │   ├── gtt_orders.py   # GTT order CRUD
│   │   ├── account.py      # Account info
│   │   └── orders.py       # Alpaca orders
│   ├── gtt_service.py      # GTT order business logic
│   ├── models.py           # SQLAlchemy models
│   ├── config.py           # Settings from .env
│   └── database/           # SQLite databases
│       ├── alpaca_orders_paper.db
│       └── alpaca_orders_live.db
├── frontend/               # Next.js + React + TypeScript
│   ├── app/               # Pages
│   │   ├── page.tsx       # Home (redirects)
│   │   ├── login/         # Login page
│   │   └── gtt/           # Main GTT orders page
│   ├── components/        # React components
│   │   ├── GTTOrderCard.tsx       # Order display card
│   │   ├── AddGTTOrderModal.tsx   # Create order modal
│   │   ├── CSVUploadModal.tsx     # Bulk upload
│   │   └── PriceChart.tsx         # Price visualization
│   ├── hooks/             # React hooks
│   │   ├── useLivePrices.ts       # Real-time prices
│   │   ├── useRealtimeUpdates.ts  # SSE order updates
│   │   └── useGTTOrder*.ts        # Order management
│   └── lib/               # Utilities
│       ├── theme.ts       # Design system colors
│       ├── formatters.ts  # Currency/date formatting
│       └── types.ts       # TypeScript types
├── scripts/               # Automation scripts (see above)
└── templates/             # CSV templates for bulk upload
```

## Real-time Updates

| Channel | Purpose | Technology |
|---------|---------|------------|
| Price Stream | Live price updates | Alpaca WebSocket + HTTP fallback |
| Order Events | Status changes, fills | Server-Sent Events (SSE) |
| Heartbeat | Keep connections alive | 15s interval (Cloudflare timeout) |

## Tech Stack

- **Backend**: Python 3.11+ / FastAPI / SQLAlchemy / SQLite
- **Frontend**: Next.js 15 / React 19 / TypeScript / Tailwind CSS
- **Real-time**: Alpaca WebSocket / SSE
- **Deployment**: Cloudflare Pages (frontend) + Tunnel (backend)
- **Notifications**: WAHA (WhatsApp HTTP API)
- **Code Quality**: Ruff (linter) + Vulture (dead code detection)

## Code Quality

```bash
# Check for issues
./scripts/33-check-code-quality.sh

# Auto-fix issues
./scripts/32-fix-code-quality.sh
```

Uses **Ruff** for linting/formatting and **Vulture** for dead code detection.

## Troubleshooting

```bash
# Full reset
./scripts/30-cleanup-restart.sh

# Fix database permissions
./scripts/31-fix-db-permissions.sh

# Restart backend
pm2 restart alpaca-backend

# Check WAHA logs
docker logs waha

# Backend health check
backend/.venv/bin/python scripts/48-check-backend-health.py

# Pre-market readiness
./scripts/37-verify-gtt-readiness.sh
```

## CSV Templates

Templates for bulk order upload are in `/templates/`:
- `gtt_template.csv` - General template
- `template_crypto.csv` - Crypto orders (fractional)
- `template_stocks.csv` - Stock orders

## API Rate Limiting

- Uses debounce (500ms) for search inputs
- Alpaca API calls are rate-limited to prevent throttling
- Price updates cached to reduce API load
