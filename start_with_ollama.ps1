# Start the RAG server with Ollama embeddings
$env:OLLAMA_EMBEDDING_MODEL = "mxbai-embed-large"
$env:OLLAMA_BASE_URL = "http://localhost:11434"

Write-Host "Starting RAG server with Ollama embeddings (mxbai-embed-large - 1024 dimensions)..." -ForegroundColor Green
python main.py
