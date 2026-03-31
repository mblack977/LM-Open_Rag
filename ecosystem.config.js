// PM2 configuration for HerbGPT
module.exports = {
  apps: [{
    name: 'herbgpt',
    script: 'python',
    args: 'main.py',
    cwd: 'c:/Herb Project/LM-Open-Rag',
    interpreter: 'none',
    env: {
      OLLAMA_EMBEDDING_MODEL: 'mxbai-embed-large',
      OLLAMA_BASE_URL: 'http://localhost:11434'
    },
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '1G',
    error_file: './logs/pm2-error.log',
    out_file: './logs/pm2-out.log',
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
    restart_delay: 5000
  }]
};
