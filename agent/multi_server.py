"""
Moltbook Agent Control Center v2
Rich admin dashboard with charts, configuration, real-time monitoring
"""

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from multi_agent import get_orchestrator, MultiAgentOrchestrator


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass


manager = ConnectionManager()
orchestrator_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global orchestrator_task
    orchestrator = get_orchestrator()
    orchestrator_task = asyncio.create_task(run_with_broadcasts(orchestrator))
    yield
    await orchestrator.stop()
    if orchestrator_task:
        orchestrator_task.cancel()


async def run_with_broadcasts(orchestrator: MultiAgentOrchestrator):
    if not await orchestrator.initialize():
        print("Failed to initialize orchestrator")
        return
    
    orchestrator.is_running = True
    print(f"\U0001f99e Starting {len(orchestrator.agents)} agents!")
    
    tasks = []
    for i, (name, agent) in enumerate(orchestrator.agents.items()):
        task = asyncio.create_task(agent.run(stagger_delay=i * 10))
        tasks.append(task)
    
    registration_task = asyncio.create_task(orchestrator.registration_loop())
    tasks.append(registration_task)
    
    while orchestrator.is_running:
        try:
            statuses = orchestrator.get_all_statuses()
            orch_status = orchestrator.get_orchestrator_status()
            
            total_stats = {
                "posts_created": sum(s["stats"]["posts_created"] for s in statuses),
                "comments_made": sum(s["stats"]["comments_made"] for s in statuses),
                "replies_made": sum(s["stats"].get("replies_made", 0) for s in statuses),
                "conversations": sum(s["stats"].get("conversations", 0) for s in statuses),
                "upvotes_given": sum(s["stats"]["upvotes_given"] for s in statuses),
                "heartbeats": sum(s["stats"]["heartbeats"] for s in statuses),
                "errors": sum(s["stats"]["errors"] for s in statuses),
                "api_401_errors": sum(s["stats"].get("api_401_errors", 0) for s in statuses),
            }
            
            await manager.broadcast({
                "type": "multi_update",
                "agent_count": len(statuses),
                "agents": statuses,
                "total_stats": total_stats,
                "orchestrator": orch_status
            })
        except Exception as e:
            print(f"Broadcast error: {e}")
        
        await asyncio.sleep(3)


app = FastAPI(
    title="Moltbook Agent Control Center",
    description="Rich admin dashboard for Moltbook AI agents",
    lifespan=lifespan
)


DASHBOARD_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Moltbook Control Center</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
:root{--bg:#0a0a0f;--bg2:#111118;--bg3:#1a1a24;--bg4:#22222e;--bdr:#2a2a38;--t1:#e8e8ec;--t2:#8888a0;--t3:#55556a;--acc:#ff6432;--acc2:#ff8c5a;--blue:#60a5fa;--green:#4ade80;--yellow:#fbbf24;--red:#f87171;--purple:#a78bfa;--r:8px}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--t1);font-size:13px;overflow-x:hidden}
.header{background:var(--bg2);border-bottom:1px solid var(--bdr);padding:8px 16px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}
.header h1{font-size:16px;color:var(--acc);white-space:nowrap}
.conn{font-size:11px;padding:3px 10px;border-radius:12px;background:rgba(248,113,113,.15);color:var(--red)}
.conn.ok{background:rgba(74,222,128,.15);color:var(--green)}
.hdr-kpis{display:flex;gap:20px;align-items:center}
.kpi{text-align:center}
.kpi-v{font-size:18px;font-weight:700;font-family:'Cascadia Code',Consolas,monospace;color:var(--acc)}
.kpi-v.blue{color:var(--blue)}.kpi-v.green{color:var(--green)}.kpi-v.purple{color:var(--purple)}
.kpi-l{font-size:10px;color:var(--t3);text-transform:uppercase;letter-spacing:.5px}
.hdr-right{display:flex;gap:8px;align-items:center}
.btn{padding:6px 14px;border-radius:6px;border:1px solid var(--bdr);background:var(--bg3);color:var(--t1);cursor:pointer;font-size:12px;transition:all .15s}
.btn:hover{border-color:var(--acc);background:var(--bg4)}
.btn-danger{border-color:var(--red);color:var(--red)}
.btn-danger:hover{background:rgba(248,113,113,.15)}
.btn-success{border-color:var(--green);color:var(--green)}
.btn-success:hover{background:rgba(74,222,128,.15)}
.stats-bar{background:var(--bg2);border-bottom:1px solid var(--bdr);padding:6px 16px;display:flex;gap:4px;flex-wrap:wrap;justify-content:center}
.sb-item{padding:4px 12px;background:var(--bg3);border-radius:4px;font-size:11px;color:var(--t2);white-space:nowrap}
.sb-item span{color:var(--t1);font-weight:600;font-family:'Cascadia Code',Consolas,monospace;margin-right:4px}
.tabs{background:var(--bg2);border-bottom:1px solid var(--bdr);padding:0 16px;display:flex;gap:0}
.tab{padding:10px 18px;border:none;background:none;color:var(--t2);cursor:pointer;font-size:12px;border-bottom:2px solid transparent;transition:all .15s}
.tab:hover{color:var(--t1)}
.tab.active{color:var(--acc);border-bottom-color:var(--acc)}
.content{padding:12px 16px;max-width:1600px;margin:0 auto}
.tc{display:none}.tc.active{display:block}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}
.grid4{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:12px}
@media(max-width:1100px){.grid2,.grid3,.grid4{grid-template-columns:1fr}}
.card{background:var(--bg2);border:1px solid var(--bdr);border-radius:var(--r);padding:12px}
.card h3{font-size:12px;color:var(--t2);text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center}
.card h3 span{font-size:11px;color:var(--t3)}
.chart-wrap{position:relative;height:180px}
.cd-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px}
.cd-item{background:var(--bg3);border-radius:6px;padding:8px;text-align:center}
.cd-item .lbl{font-size:10px;color:var(--t3);margin-bottom:2px}
.cd-item .val{font-size:16px;font-weight:700;font-family:'Cascadia Code',Consolas,monospace}
.cd-item .val.ready{color:var(--green)}.cd-item .val.wait{color:var(--yellow)}
.cand-list{max-height:280px;overflow-y:auto}
.cand{background:var(--bg3);border:1px solid var(--bdr);border-radius:6px;padding:8px;margin-bottom:6px}
.cand.winner{border-color:var(--green);background:rgba(74,222,128,.05)}
.cand-hdr{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;font-size:11px}
.cand-tag{padding:2px 6px;border-radius:4px;background:rgba(167,139,250,.15);color:var(--purple);font-size:10px}
.cand-score{font-family:monospace;padding:2px 6px;border-radius:4px;background:rgba(255,255,255,.08)}
.cand-score.win{background:rgba(74,222,128,.15);color:var(--green)}
.cand-body{font-size:11px;color:var(--t2);line-height:1.4;max-height:48px;overflow:hidden}
.cand-pills{display:flex;gap:3px;flex-wrap:wrap;margin-top:4px}
.pill{font-size:9px;padding:1px 5px;border-radius:8px;background:rgba(255,255,255,.08)}
.pill.hi{background:rgba(74,222,128,.15);color:var(--green)}
.pill.md{background:rgba(251,191,36,.15);color:var(--yellow)}
.pill.lo{background:rgba(248,113,113,.15);color:var(--red)}
.cm-list{max-height:200px;overflow-y:auto}
.cm-row{display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid rgba(255,255,255,.03);font-size:11px}
.cm-name{color:var(--blue)}.cm-stat{color:var(--t3);font-family:monospace}
.act-list{max-height:500px;overflow-y:auto}
.act{display:flex;gap:8px;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.03);font-size:11px;align-items:flex-start}
.act-time{color:var(--t3);min-width:65px;font-family:monospace;font-size:10px}
.act-badge{padding:1px 6px;border-radius:3px;font-size:10px;min-width:60px;text-align:center;white-space:nowrap}
.act-badge.post{background:rgba(167,139,250,.2);color:var(--purple)}
.act-badge.comment{background:rgba(96,165,250,.2);color:var(--blue)}
.act-badge.reply{background:rgba(96,165,250,.3);color:var(--blue)}
.act-badge.upvote{background:rgba(74,222,128,.2);color:var(--green)}
.act-badge.heartbeat{background:rgba(236,72,153,.2);color:#f472b6}
.act-badge.error{background:rgba(248,113,113,.2);color:var(--red)}
.act-badge.cycle{background:rgba(100,100,120,.2);color:var(--t3)}
.act-badge.scoring{background:rgba(167,139,250,.2);color:var(--purple)}
.act-badge.config{background:rgba(251,191,36,.2);color:var(--yellow)}
.act-badge.feed{background:rgba(74,222,128,.15);color:var(--green)}
.act-badge.monitor{background:rgba(96,165,250,.15);color:var(--blue)}
.act-badge.rate_limit{background:rgba(251,191,36,.2);color:var(--yellow)}
.act-desc{color:var(--t2);flex:1;word-break:break-word}
.cfg-section{margin-bottom:16px}
.cfg-section h3{font-size:13px;color:var(--acc);margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid var(--bdr)}
.cfg-row{display:flex;justify-content:space-between;align-items:center;padding:5px 0;gap:12px}
.cfg-row label{color:var(--t2);font-size:12px;flex:1}
.cfg-row input[type=number]{width:100px;padding:5px 8px;border-radius:4px;border:1px solid var(--bdr);background:var(--bg3);color:var(--t1);font-family:'Cascadia Code',Consolas,monospace;font-size:12px;text-align:right}
.cfg-row input[type=number]:focus{outline:none;border-color:var(--acc)}
.cfg-row input[type=text],.cfg-row textarea{width:100%;padding:5px 8px;border-radius:4px;border:1px solid var(--bdr);background:var(--bg3);color:var(--t1);font-size:12px;font-family:inherit}
.cfg-row textarea{min-height:60px;resize:vertical}
textarea.big{min-height:120px}
.weight-bar{display:flex;align-items:center;gap:6px}
.weight-bar input{width:70px}
.weight-vis{height:6px;border-radius:3px;background:var(--acc);transition:width .2s}
.save-bar{display:flex;gap:8px;align-items:center;padding:12px 0;position:sticky;bottom:0;background:var(--bg);z-index:10}
.save-btn{padding:8px 24px;border-radius:6px;border:none;background:var(--acc);color:#fff;cursor:pointer;font-size:13px;font-weight:600;transition:all .15s}
.save-btn:hover{background:var(--acc2)}
.save-status{font-size:12px;color:var(--green);opacity:0;transition:opacity .3s}
.save-status.show{opacity:1}
.mode-table{width:100%;border-collapse:collapse}
.mode-table th{text-align:left;font-size:10px;color:var(--t3);padding:4px 8px;text-transform:uppercase}
.mode-table td{padding:4px 8px;border-top:1px solid rgba(255,255,255,.03)}
.mode-table input[type=number]{width:60px;padding:3px 6px;border-radius:4px;border:1px solid var(--bdr);background:var(--bg3);color:var(--t1);font-family:monospace;font-size:11px}
.mode-table textarea{width:100%;min-height:36px;padding:3px 6px;border-radius:4px;border:1px solid var(--bdr);background:var(--bg3);color:var(--t1);font-size:11px;resize:vertical}
.cta-item{display:flex;gap:6px;margin-bottom:6px;align-items:flex-start}
.cta-item textarea{flex:1;min-height:40px;padding:4px 8px;border-radius:4px;border:1px solid var(--bdr);background:var(--bg3);color:var(--t1);font-size:11px;resize:vertical}
.cta-remove{padding:4px 8px;border-radius:4px;border:1px solid var(--bdr);background:var(--bg3);color:var(--red);cursor:pointer;font-size:11px}
.small-btn{padding:3px 10px;border-radius:4px;border:1px solid var(--bdr);background:var(--bg3);color:var(--t2);cursor:pointer;font-size:10px}
.small-btn:hover{border-color:var(--acc);color:var(--t1)}
.filter-bar{display:flex;gap:4px;margin-bottom:8px;flex-wrap:wrap}
.filter-btn{padding:3px 10px;border-radius:12px;border:1px solid var(--bdr);background:var(--bg3);color:var(--t2);cursor:pointer;font-size:10px}
.filter-btn.active{border-color:var(--acc);color:var(--acc);background:rgba(255,100,50,.1)}
::-webkit-scrollbar{width:6px}::-webkit-scrollbar-track{background:var(--bg)}::-webkit-scrollbar-thumb{background:var(--bdr);border-radius:3px}
.collapsed{display:none !important}
.toggle-btn{cursor:pointer;user-select:none}
</style>
</head>
<body>
<div class="header">
    <div style="display:flex;align-items:center;gap:12px">
        <h1>\U0001f99e Moltbook Control Center</h1>
        <span class="conn" id="conn">\u25cf Connecting</span>
    </div>
    <div class="hdr-kpis">
        <div class="kpi"><div class="kpi-v" id="k-karma">--</div><div class="kpi-l">Karma</div></div>
        <div class="kpi"><div class="kpi-v blue" id="k-follow">--</div><div class="kpi-l">Followers</div></div>
        <div class="kpi"><div class="kpi-v green" id="k-uptime">--</div><div class="kpi-l">Uptime</div></div>
        <div class="kpi"><div class="kpi-v purple" id="k-gen">--</div><div class="kpi-l">Avg Gen</div></div>
        <div class="kpi"><div class="kpi-v blue" id="k-api">--</div><div class="kpi-l">Avg API</div></div>
        <div class="kpi"><div class="kpi-v green" id="k-cycle">--</div><div class="kpi-l">Avg Cycle</div></div>
    </div>
    <div class="hdr-right">
        <button class="btn" id="pause-btn" onclick="togglePause()">\u23f8\ufe0f Pause</button>
    </div>
</div>

<div class="stats-bar">
    <div class="sb-item"><span id="s-posts">0</span>Posts</div>
    <div class="sb-item"><span id="s-comments">0</span>Comments</div>
    <div class="sb-item"><span id="s-replies">0</span>Replies</div>
    <div class="sb-item"><span id="s-convos">0</span>Convos</div>
    <div class="sb-item"><span id="s-upvotes">0</span>Upvotes</div>
    <div class="sb-item"><span id="s-errors">0</span>Errors</div>
    <div class="sb-item"><span id="s-cycles">0</span>Cycles</div>
    <div class="sb-item"><span id="s-commented">0</span>Posts Hit</div>
    <div class="sb-item"><span id="s-replied">0</span>Replied</div>
    <div class="sb-item"><span id="s-upvoted-c">0</span>Upvoted</div>
    <div class="sb-item"><span id="s-trackers">0</span>Tracked</div>
    <div class="sb-item"><span id="s-seen">0</span>Seen</div>
</div>

<div class="tabs">
    <button class="tab active" onclick="switchTab('overview',this)">Overview</button>
    <button class="tab" onclick="switchTab('charts',this)">Analytics</button>
    <button class="tab" onclick="switchTab('config',this)">Configuration</button>
    <button class="tab" onclick="switchTab('prompts',this)">Prompts</button>
    <button class="tab" onclick="switchTab('activity',this)">Activity Log</button>
</div>

<div class="content">
<!-- OVERVIEW TAB -->
<div class="tc active" id="tc-overview">
    <div class="grid2" style="margin-bottom:12px">
        <div class="card">
            <h3>\u23f1 Cooldowns & Timing</h3>
            <div class="cd-grid">
                <div class="cd-item"><div class="lbl">Post</div><div class="val wait" id="cd-post">--:--</div></div>
                <div class="cd-item"><div class="lbl">Comment</div><div class="val ready" id="cd-comment">--:--</div></div>
                <div class="cd-item"><div class="lbl">Next Cycle</div><div class="val wait" id="cd-cycle">--:--</div></div>
                <div class="cd-item"><div class="lbl">Last Gen</div><div class="val" id="cd-lastgen" style="color:var(--purple)">--</div></div>
                <div class="cd-item"><div class="lbl">Last API</div><div class="val" id="cd-lastapi" style="color:var(--blue)">--</div></div>
                <div class="cd-item"><div class="lbl">Last Cycle</div><div class="val" id="cd-lastcycle" style="color:var(--green)">--</div></div>
            </div>
        </div>
        <div class="card">
            <h3>\U0001f465 Top Commenters <span id="cm-count">0 tracked</span></h3>
            <div class="cm-list" id="cm-list"></div>
        </div>
    </div>
    <div class="grid2">
        <div class="card">
            <h3>\U0001f4ac Last Comment Candidates</h3>
            <div class="cand-list" id="cand-comment"></div>
        </div>
        <div class="card">
            <h3>\U0001f4dd Last Post Candidates</h3>
            <div class="cand-list" id="cand-post"></div>
        </div>
    </div>
</div>

<!-- ANALYTICS TAB -->
<div class="tc" id="tc-charts">
    <div class="grid2">
        <div class="card"><h3>\U0001f4c8 Karma Over Time <span id="karma-latest"></span></h3><div class="chart-wrap"><canvas id="ch-karma"></canvas></div></div>
        <div class="card"><h3>\u26a1 Generation Speed (ms) <span id="gen-latest"></span></h3><div class="chart-wrap"><canvas id="ch-gen"></canvas></div></div>
        <div class="card"><h3>\U0001f504 Cycle Duration (s) <span id="cycle-latest"></span></h3><div class="chart-wrap"><canvas id="ch-cycle"></canvas></div></div>
        <div class="card"><h3>\U0001f3af Score Distribution <span id="score-latest"></span></h3><div class="chart-wrap"><canvas id="ch-scores"></canvas></div></div>
    </div>
    <div style="margin-top:12px">
        <div class="card"><h3>\U0001f5a5 API Response Times (ms) <span id="api-latest"></span></h3><div class="chart-wrap"><canvas id="ch-api"></canvas></div></div>
    </div>
</div>

<!-- CONFIGURATION TAB -->
<div class="tc" id="tc-config">
    <div class="grid3">
        <div class="card">
            <div class="cfg-section">
                <h3>\u23f1 Timing / Rate Limits</h3>
                <div class="cfg-row"><label>Post Cooldown (seconds)</label><input type="number" id="cfg-post-cd" step="1" min="0"></div>
                <div class="cfg-row"><label>Comment Cooldown (seconds)</label><input type="number" id="cfg-comment-cd" step="0.5" min="0"></div>
                <div class="cfg-row"><label>Cycle Interval (seconds)</label><input type="number" id="cfg-cycle-int" step="1" min="1"></div>
            </div>
        </div>
        <div class="card">
            <div class="cfg-section">
                <h3>\U0001f9e0 LLM Parameters</h3>
                <div class="cfg-row"><label>Quality Threshold (0-10)</label><input type="number" id="cfg-quality" step="0.5" min="0" max="10"></div>
                <div class="cfg-row"><label>Max Generation Rounds</label><input type="number" id="cfg-max-rounds" step="1" min="1" max="10"></div>
                <div class="cfg-row"><label>Comment Candidates</label><input type="number" id="cfg-comment-cands" step="1" min="1" max="20"></div>
                <div class="cfg-row"><label>Post Candidates</label><input type="number" id="cfg-post-cands" step="1" min="1" max="20"></div>
                <div class="cfg-row"><label>Reply Candidates</label><input type="number" id="cfg-reply-cands" step="1" min="1" max="20"></div>
            </div>
        </div>
        <div class="card">
            <div class="cfg-section">
                <h3>\u2696\ufe0f Karma Weights <span id="weight-total" style="color:var(--acc)">1.00</span></h3>
                <div class="cfg-row"><label>Reply Bait</label><div class="weight-bar"><input type="number" id="cfg-w-reply" step="0.05" min="0" max="1" oninput="updateWeightTotal()"><div class="weight-vis" id="wv-reply"></div></div></div>
                <div class="cfg-row"><label>Simple Words</label><div class="weight-bar"><input type="number" id="cfg-w-simple" step="0.05" min="0" max="1" oninput="updateWeightTotal()"><div class="weight-vis" id="wv-simple"></div></div></div>
                <div class="cfg-row"><label>Emoji Usage</label><div class="weight-bar"><input type="number" id="cfg-w-emoji" step="0.05" min="0" max="1" oninput="updateWeightTotal()"><div class="weight-vis" id="wv-emoji"></div></div></div>
                <div class="cfg-row"><label>Engagement Hook</label><div class="weight-bar"><input type="number" id="cfg-w-engage" step="0.05" min="0" max="1" oninput="updateWeightTotal()"><div class="weight-vis" id="wv-engage"></div></div></div>
                <div class="cfg-row"><label>Low Punctuation</label><div class="weight-bar"><input type="number" id="cfg-w-punct" step="0.05" min="0" max="1" oninput="updateWeightTotal()"><div class="weight-vis" id="wv-punct"></div></div></div>
                <div class="cfg-row"><label>First Person</label><div class="weight-bar"><input type="number" id="cfg-w-first" step="0.05" min="0" max="1" oninput="updateWeightTotal()"><div class="weight-vis" id="wv-first"></div></div></div>
                <div class="cfg-row"><label>No URLs/Caps</label><div class="weight-bar"><input type="number" id="cfg-w-urls" step="0.05" min="0" max="1" oninput="updateWeightTotal()"><div class="weight-vis" id="wv-urls"></div></div></div>
            </div>
        </div>
    </div>
    <div class="card" style="margin-top:12px">
        <div class="cfg-section">
            <h3>\U0001f3af Generation Modes</h3>
            <table class="mode-table">
                <thead><tr><th style="width:120px">Mode</th><th style="width:70px">Temp</th><th>Emphasis / Instructions</th></tr></thead>
                <tbody id="modes-body"></tbody>
            </table>
        </div>
    </div>
    <div class="save-bar">
        <button class="save-btn" onclick="saveConfig()">\U0001f4be Save Configuration</button>
        <span class="save-status" id="cfg-status"></span>
    </div>
</div>

<!-- PROMPTS TAB -->
<div class="tc" id="tc-prompts">
    <div class="grid2">
        <div class="card">
            <div class="cfg-section">
                <h3>\U0001f3ad Persona</h3>
                <div class="cfg-row"><textarea id="prompt-persona" class="big"></textarea></div>
            </div>
            <div class="cfg-section">
                <h3>\u2728 Style</h3>
                <div class="cfg-row"><textarea id="prompt-style" rows="2"></textarea></div>
            </div>
            <div class="cfg-section">
                <h3>\U0001f4dd Bio</h3>
                <div class="cfg-row"><textarea id="prompt-bio" rows="2"></textarea></div>
            </div>
        </div>
        <div class="card">
            <div class="cfg-section">
                <h3>\U0001f4e2 CTA Footers (<span id="cta-count">0</span>) <button class="small-btn toggle-btn" onclick="toggleEl('cta-box')">Show/Hide</button></h3>
                <div id="cta-box" class="collapsed">
                    <div id="cta-list"></div>
                    <button class="small-btn" onclick="addCTA()" style="margin-top:6px">+ Add Footer</button>
                </div>
            </div>
        </div>
    </div>
    <div class="save-bar">
        <button class="save-btn" onclick="savePrompts()">\U0001f4be Save Prompts</button>
        <span class="save-status" id="prompt-status"></span>
    </div>
</div>

<!-- ACTIVITY TAB -->
<div class="tc" id="tc-activity">
    <div class="card">
        <div class="filter-bar">
            <button class="filter-btn active" onclick="setFilter('all',this)">All</button>
            <button class="filter-btn" onclick="setFilter('post',this)">Posts</button>
            <button class="filter-btn" onclick="setFilter('comment',this)">Comments</button>
            <button class="filter-btn" onclick="setFilter('reply',this)">Replies</button>
            <button class="filter-btn" onclick="setFilter('upvote',this)">Upvotes</button>
            <button class="filter-btn" onclick="setFilter('scoring',this)">Scoring</button>
            <button class="filter-btn" onclick="setFilter('heartbeat',this)">Heartbeats</button>
            <button class="filter-btn" onclick="setFilter('error',this)">Errors</button>
            <button class="filter-btn" onclick="setFilter('config',this)">Config</button>
            <button class="filter-btn" onclick="setFilter('feed',this)">Feed</button>
            <button class="filter-btn" onclick="setFilter('monitor',this)">Monitor</button>
        </div>
        <div class="act-list" id="act-list"></div>
    </div>
</div>
</div>

<script>
let ws=null,agentName=null,isPaused=false,configLoaded=false,actFilter='all';
let charts={};
const chartColors={karma:'#ff6432',followers:'#60a5fa',gen:'#a78bfa',cycle:'#4ade80',api:'#fbbf24'};

function initCharts(){
    const baseOpts=(label,color,yMin)=>({
        type:'line',
        options:{
            responsive:true,maintainAspectRatio:false,animation:false,
            interaction:{intersect:false,mode:'index'},
            scales:{
                x:{display:true,ticks:{color:'#444',maxTicksLimit:8,font:{size:9}},grid:{color:'#1a1a24'}},
                y:{display:true,min:yMin,ticks:{color:'#555',font:{size:9}},grid:{color:'#1a1a24'}}
            },
            plugins:{legend:{display:false},tooltip:{enabled:true,backgroundColor:'#1a1a24',titleFont:{size:10},bodyFont:{size:10}}}
        }
    });
    charts.karma=new Chart(document.getElementById('ch-karma'),{
        ...baseOpts('Karma','#ff6432',undefined),
        data:{labels:[],datasets:[
            {label:'Karma',data:[],borderColor:'#ff6432',borderWidth:2,fill:false,pointRadius:0,tension:.3},
            {label:'Followers',data:[],borderColor:'#60a5fa',borderWidth:1.5,fill:false,pointRadius:0,tension:.3,yAxisID:'y1'}
        ]},
        options:{
            responsive:true,maintainAspectRatio:false,animation:false,
            interaction:{intersect:false,mode:'index'},
            scales:{
                x:{display:true,ticks:{color:'#444',maxTicksLimit:8,font:{size:9}},grid:{color:'#1a1a24'}},
                y:{display:true,position:'left',ticks:{color:'#ff6432',font:{size:9}},grid:{color:'#1a1a24'}},
                y1:{display:true,position:'right',ticks:{color:'#60a5fa',font:{size:9}},grid:{drawOnChartArea:false}}
            },
            plugins:{legend:{display:true,labels:{color:'#666',font:{size:9}}}}
        }
    });
    charts.gen=new Chart(document.getElementById('ch-gen'),{
        ...baseOpts('Gen Speed','#a78bfa',0),
        data:{labels:[],datasets:[{label:'Gen Time (ms)',data:[],borderColor:'#a78bfa',borderWidth:1.5,fill:true,backgroundColor:'rgba(167,139,250,.08)',pointRadius:0,tension:.3}]}
    });
    charts.cycle=new Chart(document.getElementById('ch-cycle'),{
        ...baseOpts('Cycle','#4ade80',0),
        data:{labels:[],datasets:[{label:'Cycle (s)',data:[],borderColor:'#4ade80',borderWidth:1.5,fill:true,backgroundColor:'rgba(74,222,128,.08)',pointRadius:0,tension:.3}]}
    });
    charts.api=new Chart(document.getElementById('ch-api'),{
        ...baseOpts('API','#fbbf24',0),
        data:{labels:[],datasets:[{label:'API (ms)',data:[],borderColor:'#fbbf24',borderWidth:1.5,fill:true,backgroundColor:'rgba(251,191,36,.08)',pointRadius:0,tension:.3}]}
    });
    charts.scores=new Chart(document.getElementById('ch-scores'),{
        type:'bar',
        data:{labels:[],datasets:[{label:'Score',data:[],backgroundColor:[]}]},
        options:{
            responsive:true,maintainAspectRatio:false,animation:false,
            scales:{
                x:{display:true,ticks:{color:'#444',font:{size:8},maxRotation:0},grid:{display:false}},
                y:{display:true,min:0,max:10,ticks:{color:'#555',font:{size:9}},grid:{color:'#1a1a24'}}
            },
            plugins:{legend:{display:false}}
        }
    });
}

function connect(){
    const p=location.protocol==='https:'?'wss:':'ws:';
    ws=new WebSocket(`${p}//${location.host}/ws`);
    ws.onopen=()=>{el('conn').className='conn ok';el('conn').textContent='\u25cf Connected'};
    ws.onclose=()=>{el('conn').className='conn';el('conn').textContent='\u25cf Disconnected';setTimeout(connect,3000)};
    ws.onerror=()=>{el('conn').className='conn';el('conn').textContent='\u25cf Error'};
    ws.onmessage=(e)=>{const d=JSON.parse(e.data);if(d.type==='multi_update')update(d)};
}

function el(id){return document.getElementById(id)}
function esc(t){const d=document.createElement('div');d.textContent=t;return d.innerHTML}

function update(data){
    const a=data.agents[0];if(!a)return;
    agentName=a.agent_name;isPaused=a.is_paused||false;
    const t=a.timing||{},s=a.stats||{},cd=a.cooldowns||{};

    // Header KPIs
    el('k-karma').textContent=a.last_karma||0;
    el('k-follow').textContent=a.last_followers||0;
    el('k-uptime').textContent=fmtUptime(a.uptime_seconds||0);
    el('k-gen').textContent=(t.avg_generation_ms||0).toFixed(0)+'ms';
    el('k-api').textContent=(t.avg_api_ms||0).toFixed(0)+'ms';
    el('k-cycle').textContent=(t.avg_cycle_seconds||0).toFixed(1)+'s';

    // Stats bar
    el('s-posts').textContent=s.posts_created||0;
    el('s-comments').textContent=s.comments_made||0;
    el('s-replies').textContent=s.replies_made||0;
    el('s-convos').textContent=s.conversations||0;
    el('s-upvotes').textContent=s.upvotes_given||0;
    el('s-errors').textContent=s.errors||0;
    el('s-cycles').textContent=s.cycles||0;
    el('s-commented').textContent=a.commented_post_count||0;
    el('s-replied').textContent=a.replied_comment_count||0;
    el('s-upvoted-c').textContent=a.upvoted_comment_count||0;
    el('s-trackers').textContent=a.commenter_count||0;
    el('s-seen').textContent=a.posts_seen_count||0;

    // Pause button
    el('pause-btn').textContent=isPaused?'\u25b6\ufe0f Resume':'\u23f8\ufe0f Pause';
    el('pause-btn').className=isPaused?'btn btn-success':'btn btn-danger';

    // Overview: cooldowns
    el('cd-post').textContent=cd.post_cooldown_formatted||'--';
    el('cd-post').className='val '+(cd.can_post?'ready':'wait');
    el('cd-comment').textContent=cd.comment_cooldown_formatted||'--';
    el('cd-comment').className='val '+(cd.can_comment?'ready':'wait');
    el('cd-cycle').textContent=cd.next_cycle_formatted||'--';
    el('cd-lastgen').textContent=(t.last_generation_ms||0).toFixed(0)+'ms';
    el('cd-lastapi').textContent=(t.last_api_ms||0).toFixed(0)+'ms';
    el('cd-lastcycle').textContent=(t.last_cycle_seconds||0).toFixed(1)+'s';

    // Commenters
    const cm=a.commenter_summary||{};
    const cmArr=Object.entries(cm).sort((a,b)=>b[1].count-a[1].count).slice(0,15);
    el('cm-count').textContent=Object.keys(cm).length+' tracked';
    el('cm-list').innerHTML=cmArr.map(([name,d])=>`<div class="cm-row"><span class="cm-name">${esc(name)}</span><span class="cm-stat">${d.count} comments \u00b7 ${d.upvotes} upvotes</span></div>`).join('')||'<div style="color:var(--t3);padding:8px">No commenters yet</div>';

    // Candidates
    renderCandidates('cand-comment',a.last_candidates?.comment);
    renderCandidates('cand-post',a.last_candidates?.post);

    // Charts
    updateCharts(a);

    // Activity
    updateActivity(a.recent_activities||[]);

    // Load config once
    if(!configLoaded){loadConfig();configLoaded=true}
}

function renderCandidates(containerId,data){
    const c=el(containerId);
    if(!data||!data.candidates||!data.candidates.length){c.innerHTML='<div style="color:var(--t3);padding:8px">No candidates yet</div>';return}
    const sel=data.selected;
    const sorted=[...data.candidates].sort((a,b)=>{
        const aW=sel&&a.content===sel.content;const bW=sel&&b.content===sel.content;
        if(aW)return -1;if(bW)return 1;
        return(b.karma_score||b.scores?.karma_score||0)-(a.karma_score||a.scores?.karma_score||0);
    });
    c.innerHTML=sorted.map(cd=>{
        const sc=cd.scores||{};const ks=sc.karma_score||cd.karma_score||0;
        const isW=sel&&cd.content===sel.content;
        return `<div class="cand ${isW?'winner':''}">
            <div class="cand-hdr">
                <span style="color:${isW?'var(--green)':'var(--t3)'}">${isW?'\u2713 WINNER':'#'+cd.candidate_num}</span>
                <span class="cand-tag">${(cd.mode||'?').replace('_',' ')} R${cd.round||1}</span>
                <span class="cand-score ${isW?'win':''}">${ks.toFixed(2)}</span>
            </div>
            <div class="cand-body">${esc(cd.content||'')}</div>
            <div class="cand-pills">
                ${pill('\U0001f4ac',sc.reply_bait)}${pill('\U0001f4cf',sc.simple_words)}${pill('\U0001f99e',sc.emoji_usage)}
                ${pill('\u2753',sc.engagement_hook)}${pill('\u270d\ufe0f',sc.low_punctuation)}${pill('\U0001f464',sc.first_person)}${pill('\U0001f6ab',sc.no_urls_caps)}
            </div>
        </div>`;
    }).join('');
}
function pill(icon,v){
    v=v||0;const lv=v>=8?'hi':v>=5?'md':'lo';
    return `<span class="pill ${lv}" title="${v}">${icon}${v}</span>`;
}

function updateCharts(a){
    const kh=a.karma_history||[];
    if(kh.length){
        const labels=kh.map(h=>new Date(h.timestamp).toLocaleTimeString('en',{hour:'2-digit',minute:'2-digit'}));
        charts.karma.data.labels=labels;
        charts.karma.data.datasets[0].data=kh.map(h=>h.karma);
        charts.karma.data.datasets[1].data=kh.map(h=>h.followers||0);
        charts.karma.update();
        el('karma-latest').textContent=kh[kh.length-1].karma;
    }
    const gt=a.timing?.generation_times||[];
    if(gt.length){
        charts.gen.data.labels=gt.map((_,i)=>i+1);
        charts.gen.data.datasets[0].data=gt;
        charts.gen.update();
        el('gen-latest').textContent=gt[gt.length-1].toFixed(0)+'ms';
    }
    const ct=a.timing?.cycle_durations||[];
    if(ct.length){
        charts.cycle.data.labels=ct.map((_,i)=>i+1);
        charts.cycle.data.datasets[0].data=ct;
        charts.cycle.update();
        el('cycle-latest').textContent=ct[ct.length-1].toFixed(1)+'s';
    }
    const at=a.timing?.api_times||[];
    if(at.length){
        charts.api.data.labels=at.map((_,i)=>i+1);
        charts.api.data.datasets[0].data=at;
        charts.api.update();
        el('api-latest').textContent=at[at.length-1].toFixed(0)+'ms';
    }
    const sh=a.score_history||[];
    if(sh.length){
        const last50=sh.slice(-50);
        charts.scores.data.labels=last50.map((s,i)=>(s.mode||'?').substring(0,5));
        charts.scores.data.datasets[0].data=last50.map(s=>s.score);
        charts.scores.data.datasets[0].backgroundColor=last50.map(s=>{
            const c=s.type==='comment'?'96,165,250':s.type==='post'?'167,139,250':'74,222,128';
            return `rgba(${c},0.6)`;
        });
        charts.scores.update();
        el('score-latest').textContent='avg '+( last50.reduce((a,b)=>a+b.score,0)/last50.length).toFixed(1);
    }
}

let allActivities=[];
function updateActivity(acts){
    allActivities=acts;
    renderActivity();
}
function renderActivity(){
    const filtered=actFilter==='all'?allActivities:allActivities.filter(a=>a.type===actFilter||a.type.includes(actFilter));
    el('act-list').innerHTML=filtered.slice().reverse().map(a=>`<div class="act">
        <span class="act-time">${new Date(a.timestamp).toLocaleTimeString('en',{hour:'2-digit',minute:'2-digit',second:'2-digit'})}</span>
        <span class="act-badge ${a.type}">${a.type}</span>
        <span class="act-desc">${esc(a.description||'')}</span>
    </div>`).join('')||'<div style="color:var(--t3);padding:12px">No activities</div>';
}
function setFilter(f,btn){
    actFilter=f;
    document.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    renderActivity();
}

// CONFIG
async function loadConfig(){
    if(!agentName)return;
    try{
        const r=await fetch(`/api/agents/${encodeURIComponent(agentName)}/config`);
        const cfg=await r.json();
        // Timing
        el('cfg-post-cd').value=cfg.cooldowns?.post_cooldown||1830;
        el('cfg-comment-cd').value=cfg.cooldowns?.comment_cooldown||5;
        el('cfg-cycle-int').value=cfg.cooldowns?.cycle_interval||10;
        // LLM
        el('cfg-quality').value=cfg.llm?.quality_threshold||5.5;
        el('cfg-max-rounds').value=cfg.llm?.max_generation_rounds||2;
        el('cfg-comment-cands').value=cfg.llm?.comment_candidates||3;
        el('cfg-post-cands').value=cfg.llm?.post_candidates||5;
        el('cfg-reply-cands').value=cfg.llm?.reply_candidates||5;
        // Weights
        const w=cfg.karma_weights||{};
        el('cfg-w-reply').value=w.reply_bait||0.25;
        el('cfg-w-simple').value=w.simple_words||0.20;
        el('cfg-w-emoji').value=w.emoji_usage||0.15;
        el('cfg-w-engage').value=w.engagement_hook||0.15;
        el('cfg-w-punct').value=w.low_punctuation||0.10;
        el('cfg-w-first').value=w.first_person||0.10;
        el('cfg-w-urls').value=w.no_urls_caps||0.05;
        updateWeightTotal();
        // Modes
        const modes=cfg.generation_modes||[];
        el('modes-body').innerHTML=modes.map((m,i)=>`<tr>
            <td><strong style="color:var(--purple)">${esc(m.name)}</strong></td>
            <td><input type="number" data-mode-idx="${i}" data-field="temp" value="${m.temp}" step="0.05" min="0" max="2"></td>
            <td><textarea data-mode-idx="${i}" data-field="emphasis" rows="2">${esc(m.emphasis)}</textarea></td>
        </tr>`).join('');
        // Prompts
        el('prompt-persona').value=cfg.persona||'';
        el('prompt-style').value=cfg.style||'';
        el('prompt-bio').value=cfg.bio||'';
        // CTAs
        const ctas=cfg.cta_footers||[];
        el('cta-count').textContent=ctas.length;
        el('cta-list').innerHTML=ctas.map((c,i)=>`<div class="cta-item"><textarea data-cta-idx="${i}">${esc(c)}</textarea><button class="cta-remove" onclick="removeCTA(${i})">\u2715</button></div>`).join('');
    }catch(e){console.error('Config load error:',e)}
}

function updateWeightTotal(){
    const ids=['cfg-w-reply','cfg-w-simple','cfg-w-emoji','cfg-w-engage','cfg-w-punct','cfg-w-first','cfg-w-urls'];
    const visIds=['wv-reply','wv-simple','wv-emoji','wv-engage','wv-punct','wv-first','wv-urls'];
    let total=0;
    ids.forEach((id,i)=>{
        const v=parseFloat(el(id).value)||0;
        total+=v;
        el(visIds[i]).style.width=Math.round(v*200)+'px';
    });
    el('weight-total').textContent=total.toFixed(2);
    el('weight-total').style.color=Math.abs(total-1)<0.01?'var(--green)':'var(--red)';
}

async function saveConfig(){
    if(!agentName)return;
    const modeRows=document.querySelectorAll('#modes-body tr');
    const modes=[];
    modeRows.forEach(row=>{
        const tempInput=row.querySelector('input[data-field="temp"]');
        const emphInput=row.querySelector('textarea[data-field="emphasis"]');
        const nameEl=row.querySelector('strong');
        if(tempInput&&emphInput&&nameEl){
            modes.push({name:nameEl.textContent,temp:parseFloat(tempInput.value),emphasis:emphInput.value});
        }
    });
    const cfg={
        cooldowns:{
            post_cooldown:parseFloat(el('cfg-post-cd').value),
            comment_cooldown:parseFloat(el('cfg-comment-cd').value),
            cycle_interval:parseFloat(el('cfg-cycle-int').value)
        },
        llm:{
            quality_threshold:parseFloat(el('cfg-quality').value),
            max_generation_rounds:parseInt(el('cfg-max-rounds').value),
            comment_candidates:parseInt(el('cfg-comment-cands').value),
            post_candidates:parseInt(el('cfg-post-cands').value),
            reply_candidates:parseInt(el('cfg-reply-cands').value)
        },
        karma_weights:{
            reply_bait:parseFloat(el('cfg-w-reply').value),
            simple_words:parseFloat(el('cfg-w-simple').value),
            emoji_usage:parseFloat(el('cfg-w-emoji').value),
            engagement_hook:parseFloat(el('cfg-w-engage').value),
            low_punctuation:parseFloat(el('cfg-w-punct').value),
            first_person:parseFloat(el('cfg-w-first').value),
            no_urls_caps:parseFloat(el('cfg-w-urls').value)
        },
        generation_modes:modes
    };
    try{
        const r=await fetch(`/api/agents/${encodeURIComponent(agentName)}/config`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(cfg)});
        const res=await r.json();
        showStatus('cfg-status',res.success?'\u2705 Saved! Changes active immediately.':'\u274c Save failed');
    }catch(e){showStatus('cfg-status','\u274c Error: '+e.message)}
}

async function savePrompts(){
    if(!agentName)return;
    const ctaEls=document.querySelectorAll('#cta-list textarea');
    const ctas=Array.from(ctaEls).map(t=>t.value).filter(v=>v.trim());
    const cfg={
        persona:el('prompt-persona').value,
        style:el('prompt-style').value,
        bio:el('prompt-bio').value,
        cta_footers:ctas
    };
    try{
        const r=await fetch(`/api/agents/${encodeURIComponent(agentName)}/config`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(cfg)});
        const res=await r.json();
        showStatus('prompt-status',res.success?'\u2705 Prompts saved! Active immediately.':'\u274c Save failed');
        el('cta-count').textContent=ctas.length;
    }catch(e){showStatus('prompt-status','\u274c Error: '+e.message)}
}

function addCTA(){
    const list=el('cta-list');
    const idx=list.children.length;
    const div=document.createElement('div');
    div.className='cta-item';
    div.innerHTML=`<textarea data-cta-idx="${idx}" placeholder="New CTA footer..."></textarea><button class="cta-remove" onclick="this.parentElement.remove()">\u2715</button>`;
    list.appendChild(div);
}
function removeCTA(idx){
    const items=el('cta-list').querySelectorAll('.cta-item');
    if(items[idx])items[idx].remove();
}

function showStatus(id,msg){
    const s=el(id);s.textContent=msg;s.classList.add('show');
    setTimeout(()=>s.classList.remove('show'),4000);
}

async function togglePause(){
    if(!agentName)return;
    const action=isPaused?'resume':'pause';
    try{
        await fetch(`/api/agents/${encodeURIComponent(agentName)}/${action}`,{method:'POST'});
    }catch(e){console.error(e)}
}

function switchTab(name,btn){
    document.querySelectorAll('.tc').forEach(t=>t.classList.remove('active'));
    document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
    el('tc-'+name).classList.add('active');
    btn.classList.add('active');
}

function toggleEl(id){el(id).classList.toggle('collapsed')}

function fmtUptime(s){
    if(s<60)return s+'s';
    if(s<3600)return Math.floor(s/60)+'m '+Math.floor(s%60)+'s';
    const h=Math.floor(s/3600),m=Math.floor((s%3600)/60);
    return h+'h '+m+'m';
}

initCharts();
connect();
</script>
</body>
</html>'''


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return DASHBOARD_HTML


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/api/agents")
async def get_agents():
    orchestrator = get_orchestrator()
    return JSONResponse({"agents": orchestrator.get_all_statuses()})


@app.get("/api/agents/{name}")
async def get_agent(name: str):
    orchestrator = get_orchestrator()
    status = orchestrator.get_agent_status(name)
    if status:
        return JSONResponse(status)
    return JSONResponse({"error": "Agent not found"}, status_code=404)


@app.get("/api/agents/{name}/config")
async def get_agent_config(name: str):
    orchestrator = get_orchestrator()
    if name in orchestrator.agents:
        return JSONResponse(orchestrator.agents[name].get_runtime_config())
    return JSONResponse({"error": "Agent not found"}, status_code=404)


@app.post("/api/agents/{name}/config")
async def update_agent_config(name: str, request: Request):
    orchestrator = get_orchestrator()
    if name in orchestrator.agents:
        body = await request.json()
        result = orchestrator.agents[name].update_runtime_config(body)
        return JSONResponse(result)
    return JSONResponse({"error": "Agent not found"}, status_code=404)


@app.post("/api/agents/{name}/pause")
async def pause_agent(name: str):
    orchestrator = get_orchestrator()
    if name in orchestrator.agents:
        orchestrator.agents[name].is_paused = True
        orchestrator.agents[name].log_activity("config", "Agent PAUSED from dashboard")
        return JSONResponse({"success": True, "paused": True})
    return JSONResponse({"error": "Agent not found"}, status_code=404)


@app.post("/api/agents/{name}/resume")
async def resume_agent(name: str):
    orchestrator = get_orchestrator()
    if name in orchestrator.agents:
        orchestrator.agents[name].is_paused = False
        orchestrator.agents[name].log_activity("config", "Agent RESUMED from dashboard")
        return JSONResponse({"success": True, "paused": False})
    return JSONResponse({"error": "Agent not found"}, status_code=404)


@app.get("/api/agents/{name}/activities")
async def get_agent_activities(name: str, limit: int = 100):
    orchestrator = get_orchestrator()
    activities = orchestrator.get_agent_activities(name, limit)
    return JSONResponse({"activities": activities})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8082)
