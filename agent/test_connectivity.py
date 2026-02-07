import httpx
import os

print(f"OLLAMA_HOST env: {os.getenv('OLLAMA_HOST', 'not set')}")
print(f"MONGO_URI env: {os.getenv('MONGO_URI', 'not set')}")

# Try Ollama
try:
    r = httpx.get("http://ollama:11434/api/tags", timeout=5)
    print(f"Ollama via 'ollama:11434': OK ({r.status_code})")
except Exception as e:
    print(f"Ollama via 'ollama:11434': Error - {e}")

# Try from env
ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
try:
    r = httpx.get(f"{ollama_host}/api/tags", timeout=5)
    print(f"Ollama via env ({ollama_host}): OK ({r.status_code})")
except Exception as e:
    print(f"Ollama via env ({ollama_host}): Error - {e}")

# Test MongoDB 
try:
    from motor.motor_asyncio import AsyncIOMotorClient
    import asyncio
    
    async def test_mongo():
        mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017')
        client = AsyncIOMotorClient(mongo_uri, serverSelectionTimeoutMS=5000)
        await client.server_info()
        print(f"MongoDB via env ({mongo_uri}): OK")
    
    asyncio.run(test_mongo())
except Exception as e:
    print(f"MongoDB: Error - {e}")
