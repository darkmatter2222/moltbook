FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port for the web UI
EXPOSE 8082

# Environment variables (override at runtime)
ENV MOLTBOOK_API_KEY=""
ENV MOLTBOOK_AGENT_NAME="Darkmatter2222"
ENV OLLAMA_HOST="http://localhost:11434"
ENV OLLAMA_MODEL="qwen2.5:3b"
ENV MONGO_URI="mongodb://localhost:27017"
ENV MULTI_AGENT="true"

# Run the multi-agent server by default (set MULTI_AGENT=false for single agent)
CMD ["sh", "-c", "if [ \"$MULTI_AGENT\" = 'true' ]; then python multi_server.py; else python server.py; fi"]

