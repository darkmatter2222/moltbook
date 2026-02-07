"""
FastAPI Web Server for Moltbook Agent
Provides real-time activity monitoring UI and API
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from moltbook_agent import get_agent, MoltbookSupremeAgent


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass


manager = ConnectionManager()
agent_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global agent_task
    agent = get_agent()
    
    # Start the agent in the background
    agent_task = asyncio.create_task(run_agent_with_broadcasts(agent))
    
    yield
    
    # Shutdown
    agent.stop()
    if agent_task:
        agent_task.cancel()


async def run_agent_with_broadcasts(agent: MoltbookSupremeAgent):
    """Run agent and broadcast activity updates"""
    agent.is_running = True
    
    while agent.is_running:
        try:
            await agent.run_cycle()
            
            # Broadcast status update to all connected clients
            status = agent.get_status()
            activities = await agent.activity_log.get_recent(20)
            await manager.broadcast({
                "type": "update",
                "status": status,
                "activities": activities
            })
            
        except Exception as e:
            print(f"Agent cycle error: {e}")
        
        # Wait 30 seconds between cycles for MAXIMUM activity
        await asyncio.sleep(30)


app = FastAPI(
    title="Moltbook Agent Dashboard",
    description="Real-time monitoring for your Moltbook AI agent",
    lifespan=lifespan
)


# HTML Dashboard
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🦞 Moltbook Agent Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e0e0e0;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 0;
            border-bottom: 1px solid #333;
            margin-bottom: 30px;
        }
        
        h1 {
            font-size: 2rem;
            color: #ff6b6b;
        }
        
        h1 span {
            color: #ffd93d;
        }
        
        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: 500;
        }
        
        .status-badge.running {
            background: rgba(0, 255, 136, 0.2);
            color: #00ff88;
        }
        
        .status-badge.stopped {
            background: rgba(255, 107, 107, 0.2);
            color: #ff6b6b;
        }
        
        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        
        .status-dot.running {
            background: #00ff88;
        }
        
        .status-dot.stopped {
            background: #ff6b6b;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 20px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .stat-card h3 {
            font-size: 0.85rem;
            color: #888;
            text-transform: uppercase;
            margin-bottom: 8px;
        }
        
        .stat-card .value {
            font-size: 2rem;
            font-weight: 700;
            color: #fff;
        }
        
        .stat-card.karma .value {
            color: #ffd93d;
        }
        
        .stat-card.posts .value {
            color: #4ecdc4;
        }
        
        .stat-card.comments .value {
            color: #95afc0;
        }
        
        .stat-card.upvotes .value {
            color: #ff6b6b;
        }
        
        .activity-section {
            background: rgba(255, 255, 255, 0.03);
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            overflow: hidden;
        }
        
        .activity-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .activity-header h2 {
            font-size: 1.2rem;
        }
        
        .activity-list {
            max-height: 500px;
            overflow-y: auto;
        }
        
        .activity-item {
            display: flex;
            align-items: flex-start;
            gap: 15px;
            padding: 15px 20px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            transition: background 0.2s;
        }
        
        .activity-item:hover {
            background: rgba(255, 255, 255, 0.05);
        }
        
        .activity-icon {
            width: 36px;
            height: 36px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.1rem;
            flex-shrink: 0;
        }
        
        .activity-icon.post { background: rgba(78, 205, 196, 0.2); }
        .activity-icon.comment { background: rgba(149, 175, 192, 0.2); }
        .activity-icon.upvote { background: rgba(255, 107, 107, 0.2); }
        .activity-icon.heartbeat { background: rgba(255, 217, 61, 0.2); }
        .activity-icon.check_feed { background: rgba(108, 92, 231, 0.2); }
        .activity-icon.check_dms { background: rgba(0, 206, 201, 0.2); }
        .activity-icon.llm_query { background: rgba(129, 236, 236, 0.2); }
        .activity-icon.error { background: rgba(255, 71, 87, 0.2); }
        
        .activity-content {
            flex: 1;
        }
        
        .activity-content p {
            margin-bottom: 4px;
        }
        
        .activity-content .time {
            font-size: 0.8rem;
            color: #666;
        }
        
        .activity-content .details {
            font-size: 0.85rem;
            color: #888;
            margin-top: 5px;
        }
        
        .connection-status {
            position: fixed;
            bottom: 20px;
            right: 20px;
            padding: 10px 20px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 500;
        }
        
        .connection-status.connected {
            background: rgba(0, 255, 136, 0.2);
            color: #00ff88;
        }
        
        .connection-status.disconnected {
            background: rgba(255, 107, 107, 0.2);
            color: #ff6b6b;
        }
        
        .agent-info {
            display: flex;
            align-items: center;
            gap: 15px;
            margin-bottom: 30px;
            padding: 20px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
        }
        
        .agent-avatar {
            width: 60px;
            height: 60px;
            border-radius: 12px;
            background: linear-gradient(135deg, #ff6b6b, #ffd93d);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2rem;
        }
        
        .agent-details h2 {
            color: #fff;
            margin-bottom: 5px;
        }
        
        .agent-details p {
            color: #888;
            font-size: 0.9rem;
        }
        
        .refresh-btn {
            background: rgba(255, 255, 255, 0.1);
            border: none;
            padding: 8px 16px;
            border-radius: 8px;
            color: #fff;
            cursor: pointer;
            transition: background 0.2s;
        }
        
        .refresh-btn:hover {
            background: rgba(255, 255, 255, 0.2);
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🦞 <span>Moltbook</span> Agent</h1>
            <div id="agent-status" class="status-badge stopped">
                <div class="status-dot stopped"></div>
                <span>Connecting...</span>
            </div>
        </header>
        
        <div class="agent-info">
            <div class="agent-avatar">🤖</div>
            <div class="agent-details">
                <h2 id="agent-name">Darkmatter2222</h2>
                <p id="agent-model">Qwen 2.5 3B • Kubernetes • RTX 3090</p>
            </div>
        </div>
        
        <div class="grid">
            <div class="stat-card karma">
                <h3>Karma</h3>
                <div class="value" id="stat-karma">-</div>
            </div>
            <div class="stat-card posts">
                <h3>Posts Created</h3>
                <div class="value" id="stat-posts">0</div>
            </div>
            <div class="stat-card comments">
                <h3>Comments Made</h3>
                <div class="value" id="stat-comments">0</div>
            </div>
            <div class="stat-card upvotes">
                <h3>Upvotes Given</h3>
                <div class="value" id="stat-upvotes">0</div>
            </div>
            <div class="stat-card">
                <h3>Heartbeats</h3>
                <div class="value" id="stat-heartbeats">0</div>
            </div>
            <div class="stat-card">
                <h3>Errors</h3>
                <div class="value" id="stat-errors">0</div>
            </div>
        </div>
        
        <div class="activity-section">
            <div class="activity-header">
                <h2>📡 Real-time Activity</h2>
                <button class="refresh-btn" onclick="refreshData()">↻ Refresh</button>
            </div>
            <div class="activity-list" id="activity-list">
                <div class="activity-item">
                    <div class="activity-icon heartbeat">⏳</div>
                    <div class="activity-content">
                        <p>Waiting for agent activity...</p>
                        <span class="time">Connecting to WebSocket...</span>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div id="connection-status" class="connection-status disconnected">
        ● Disconnected
    </div>
    
    <script>
        let ws = null;
        let reconnectAttempts = 0;
        
        const activityIcons = {
            'post': '📝',
            'comment': '💬',
            'upvote': '⬆️',
            'downvote': '⬇️',
            'check_feed': '📰',
            'check_dms': '✉️',
            'reply_dm': '↩️',
            'follow': '👋',
            'heartbeat': '💓',
            'llm_query': '🧠',
            'error': '❌'
        };
        
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
            
            ws.onopen = () => {
                console.log('WebSocket connected');
                reconnectAttempts = 0;
                updateConnectionStatus(true);
                refreshData();
            };
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                handleUpdate(data);
            };
            
            ws.onclose = () => {
                console.log('WebSocket disconnected');
                updateConnectionStatus(false);
                
                // Reconnect with exponential backoff
                const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);
                reconnectAttempts++;
                setTimeout(connectWebSocket, delay);
            };
            
            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
        }
        
        function updateConnectionStatus(connected) {
            const el = document.getElementById('connection-status');
            if (connected) {
                el.className = 'connection-status connected';
                el.textContent = '● Connected';
            } else {
                el.className = 'connection-status disconnected';
                el.textContent = '● Disconnected';
            }
        }
        
        function handleUpdate(data) {
            if (data.type === 'update' || data.type === 'status') {
                updateStatus(data.status);
                if (data.activities) {
                    updateActivities(data.activities);
                }
            }
        }
        
        function updateStatus(status) {
            if (!status) return;
            
            // Update agent status badge
            const statusBadge = document.getElementById('agent-status');
            const statusDot = statusBadge.querySelector('.status-dot');
            const statusText = statusBadge.querySelector('span');
            
            if (status.is_running) {
                statusBadge.className = 'status-badge running';
                statusDot.className = 'status-dot running';
                statusText.textContent = 'Running';
            } else {
                statusBadge.className = 'status-badge stopped';
                statusDot.className = 'status-dot stopped';
                statusText.textContent = 'Stopped';
            }
            
            // Update agent name
            if (status.agent_name) {
                document.getElementById('agent-name').textContent = status.agent_name;
            }
            
            // Update model info
            if (status.ollama_model) {
                document.getElementById('agent-model').textContent = 
                    `${status.ollama_model} • Kubernetes • RTX 3090`;
            }
            
            // Update stats
            if (status.stats) {
                document.getElementById('stat-posts').textContent = status.stats.posts_created || 0;
                document.getElementById('stat-comments').textContent = status.stats.comments_made || 0;
                document.getElementById('stat-upvotes').textContent = status.stats.upvotes_given || 0;
                document.getElementById('stat-heartbeats').textContent = status.stats.heartbeats || 0;
                document.getElementById('stat-errors').textContent = status.stats.errors || 0;
            }
            
            // Update karma if available
            if (status.karma !== undefined) {
                document.getElementById('stat-karma').textContent = status.karma;
            }
        }
        
        function updateActivities(activities) {
            const list = document.getElementById('activity-list');
            
            if (activities.length === 0) {
                list.innerHTML = `
                    <div class="activity-item">
                        <div class="activity-icon heartbeat">⏳</div>
                        <div class="activity-content">
                            <p>No activity yet...</p>
                            <span class="time">Agent is starting up</span>
                        </div>
                    </div>
                `;
                return;
            }
            
            list.innerHTML = activities.map(activity => {
                const icon = activityIcons[activity.type] || '📌';
                const time = new Date(activity.timestamp).toLocaleString();
                const detailsStr = activity.details && Object.keys(activity.details).length > 0
                    ? `<div class="details">${JSON.stringify(activity.details).slice(0, 100)}</div>`
                    : '';
                
                return `
                    <div class="activity-item">
                        <div class="activity-icon ${activity.type}">${icon}</div>
                        <div class="activity-content">
                            <p>${activity.description}</p>
                            <span class="time">${time}</span>
                            ${detailsStr}
                        </div>
                    </div>
                `;
            }).join('');
        }
        
        async function refreshData() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                handleUpdate({ type: 'status', status: data.status, activities: data.activities });
            } catch (error) {
                console.error('Failed to refresh:', error);
            }
        }
        
        // Initialize
        connectWebSocket();
        
        // Refresh every 30 seconds as backup
        setInterval(refreshData, 30000);
    </script>
</body>
</html>
'''


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the dashboard HTML"""
    return DASHBOARD_HTML


@app.get("/api/status")
async def get_status():
    """Get current agent status and recent activities"""
    agent = get_agent()
    status = agent.get_status()
    activities = await agent.activity_log.get_recent(50)
    
    return {
        "status": status,
        "activities": activities
    }


@app.get("/api/activities")
async def get_activities(limit: int = 50):
    """Get recent activities"""
    agent = get_agent()
    activities = await agent.activity_log.get_recent(limit)
    return {"activities": activities}


@app.post("/api/trigger-cycle")
async def trigger_cycle():
    """Manually trigger an activity cycle"""
    agent = get_agent()
    asyncio.create_task(agent.run_cycle())
    return {"message": "Cycle triggered"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates"""
    await manager.connect(websocket)
    
    try:
        # Send initial status
        agent = get_agent()
        status = agent.get_status()
        activities = await agent.activity_log.get_recent(20)
        await websocket.send_json({
            "type": "update",
            "status": status,
            "activities": activities
        })
        
        # Keep connection alive
        while True:
            try:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
            except WebSocketDisconnect:
                break
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
