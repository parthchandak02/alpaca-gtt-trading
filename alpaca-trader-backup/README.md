# Alpaca GTT Tracker - Frontend

Next.js frontend for the Alpaca GTT Order Tracker application.

## Tech Stack

- **Framework**: Next.js 16 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS + shadcn/ui
- **Package Manager**: pnpm

## Getting Started

### Prerequisites

- Node.js 18+ 
- pnpm installed globally (`npm install -g pnpm`)

### Installation

```bash
# Install dependencies
pnpm install
```

### Environment Variables

Create a `.env.local` file in the `frontend` directory:

```bash
API_URL=http://localhost:8000
```

Or use Next.js-specific prefix:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Development

```bash
# Start development server
pnpm dev
```

The app will be available at `http://localhost:3000`

### Build

```bash
# Build for production
pnpm build

# Start production server
pnpm start
```

## Project Structure

```
frontend/
├── app/                    # Next.js App Router pages
│   ├── login/             # Login page
│   ├── gtt/               # GTT orders dashboard
│   ├── layout.tsx         # Root layout
│   └── globals.css        # Global styles
├── components/            # React components
│   └── ui/                # shadcn/ui components
├── hooks/                 # React hooks
│   ├── useAuth.ts         # Authentication hook
│   ├── useLivePrices.ts   # Live price updates
│   └── useCompanyNames.ts  # Company name caching
├── lib/                   # Utilities
│   ├── theme.ts           # Theme configuration
│   └── utils.ts           # Utility functions
├── services/              # API client
│   └── api.ts             # Axios API client
└── middleware.ts          # Next.js middleware
```

## Features

- ✅ Authentication with password protection
- ✅ Live price updates (5s when market open, 5min when closed)
- ✅ GTT order management
- ✅ Company name caching
- ✅ **Comprehensive Glassmorphism Design System** - Easy-to-use glass effects
- ✅ Responsive layout

## Glassmorphism System

This project includes a comprehensive glassmorphism system that makes it easy to add cohesive, beautiful glass effects throughout your UI.

### Quick Usage

```tsx
import { GlassCard, GlassContainer } from '@/components/glass'

// Simple glass card
<GlassCard>
  Your content
</GlassCard>

// Glass container with variants
<GlassContainer variant="heavy" tint="blue">
  Premium content
</GlassContainer>
```

### Available Components

- **GlassCard** - Pre-styled card with hover effects
- **GlassContainer** - Flexible container with variants (light/medium/heavy) and tints
- **GlassButton** - Glass-styled button
- **GlassInput** - Glass-styled input field

### CSS Utilities

Use Tailwind classes directly:
- `.glass-card` - Card glass effect
- `.glass-light` / `.glass-medium` / `.glass-heavy` - Intensity variants
- `.glass-tint-blue` / `.glass-tint-purple` / `.glass-tint-green` - Colored tints

## Typography

Three specialized fonts:
- **Inter** - Default UI font (body, headings, labels)
- **Roboto** - Numbers and financial data (prices, amounts, quantities)
- **Roboto Mono** - Timestamps and dates (monospaced for alignment)

