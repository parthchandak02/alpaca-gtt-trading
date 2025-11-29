/**
 * PM2 Ecosystem Configuration
 * 
 * Local Development: pm2 start ecosystem.config.js
 * Production: pm2 start ecosystem.config.js --env production
 * 
 * Logging:
 * - Stdout/Stderr are merged into single log files per process (backend.log, etc)
 * - Rotation is handled by pm2-logrotate module
 * - Configured for 8MB max size, 0 retained backups (only current file kept)
 */

module.exports = {
  apps: [
    // Backend API (localhost:8000)
    {
      name: 'alpaca-backend',
      script: './scripts/11-run-backend.sh',
      cwd: '.',
      interpreter: 'bash',
      env: {
        NODE_ENV: 'development',
        PORT: 8000,
      },
      env_production: {
        NODE_ENV: 'production',
        PORT: 8000,
      },
      error_file: './logs/backend.log',
      out_file: './logs/backend.log',
      log_date_format: 'YYYY-MM-DDTHH:mm:ss',
      merge_logs: true,  // Merge logs into single file
      combine_logs: true,  // Combine stdout/stderr
      time: true,
      autorestart: true,
      // Disable PM2 watch - Python doesn't support hot-reload
      // Watch mode causes constant restarts when cache/database files are written
      watch: false,
      max_memory_restart: '500M',
      instances: 1,
      exec_mode: 'fork',
    },
    // Frontend (localhost:3000)
    {
      name: 'alpaca-frontend',
      script: './scripts/12-run-frontend.sh',
      cwd: '.',
      interpreter: 'bash',
      env: {
        NODE_ENV: 'development',
        PORT: 3000,
      },
      env_production: {
        NODE_ENV: 'production',
        PORT: 3000,
      },
      log_file: './logs/frontend.log',
      error_file: './logs/frontend.log',
      out_file: './logs/frontend.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
      combine_logs: true,
      time: true,
      autorestart: true,
      // Disable PM2 watch - Vite handles HMR internally
      // PM2 watch causes full restarts instead of hot reloads
      watch: false,
      // Don't suppress console output
      instance_var: 'INSTANCE_ID',
      max_memory_restart: '300M',
      instances: 1,
      exec_mode: 'fork',
    },
    // Cloudflare Tunnel - exposes backend API securely
    {
      name: 'alpaca-tunnel',
      script: 'cloudflared',
      args: 'tunnel --config cloudflared-config.yml run',
      cwd: '.',
      env: {
        NODE_ENV: 'production',
      },
      log_file: './logs/tunnel.log',
      error_file: './logs/tunnel.log',
      out_file: './logs/tunnel.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
      combine_logs: true,
      time: true,
      autorestart: true,
      watch: false,
      instances: 1,
      exec_mode: 'fork',
      // Wait for backend to be ready before starting tunnel
      wait_ready: false,
      // Restart delay if tunnel fails
      min_uptime: '10s',
      max_restarts: 10,
    },
  ],
}

