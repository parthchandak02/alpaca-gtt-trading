/**
 * PM2 Ecosystem Configuration (template)
 *
 * Copy to ecosystem.config.js and adjust paths for your machine:
 *   cp ecosystem.config.example.js ecosystem.config.js
 *
 * Local:  pm2 start ecosystem.config.js
 * Prod:   pm2 start ecosystem.config.js --env production
 */

module.exports = {
  apps: [
    {
      name: 'alpaca-backend',
      script: './scripts/11-run-backend.sh',
      cwd: '.',
      interpreter: 'bash',
      env: { NODE_ENV: 'development', PORT: 8000 },
      env_production: { NODE_ENV: 'production', PORT: 8000 },
      error_file: './logs/backend.log',
      out_file: './logs/backend.log',
      log_date_format: 'YYYY-MM-DDTHH:mm:ss',
      merge_logs: true,
      combine_logs: true,
      time: true,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      instances: 1,
      exec_mode: 'fork',
    },
    {
      name: 'alpaca-frontend',
      script: './scripts/12-run-frontend.sh',
      cwd: '.',
      interpreter: 'bash',
      env: { NODE_ENV: 'development', PORT: 3000 },
      env_production: { NODE_ENV: 'production', PORT: 3000 },
      log_file: './logs/frontend.log',
      error_file: './logs/frontend.log',
      out_file: './logs/frontend.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
      combine_logs: true,
      time: true,
      autorestart: true,
      watch: false,
      instance_var: 'INSTANCE_ID',
      max_memory_restart: '300M',
      instances: 1,
      exec_mode: 'fork',
    },
    {
      name: 'alpaca-tunnel',
      script: 'cloudflared',
      args: ['tunnel', '--config', './cloudflared-config.yml', 'run'],
      cwd: '.',
      env: { NODE_ENV: 'production' },
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
      max_memory_restart: '500M',
      min_uptime: '10s',
      max_restarts: 10,
    },
  ],
}
