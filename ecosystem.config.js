module.exports = {
  apps: [
    {
      name: 'ai-dashboard',
      script: 'app.js',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        NODE_ENV: 'development',
        PORT: 3000
      },
      env_production: {
        NODE_ENV: 'production',
        PORT: 3000
      },
      log_file: './logs/ai-dashboard.log',
      out_file: './logs/ai-dashboard-out.log',
      error_file: './logs/ai-dashboard-error.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
      time: true
    }
  ]
}; 