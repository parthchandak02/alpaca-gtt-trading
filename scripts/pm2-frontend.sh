#!/bin/bash
# PM2 wrapper script for frontend (Next.js)

cd "$(dirname "$0")/../frontend"

# Run pnpm dev server
exec pnpm run dev

