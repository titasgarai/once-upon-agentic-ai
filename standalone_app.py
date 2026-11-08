"""
Once Upon Agentic AI - Standalone Cloud-Ready Game Master Application
=====================================================================
Single-process, single-port deployment combining:
1. Game Master Agent (Amazon Bedrock / Claude Sonnet with Graceful Fallback)
2. Dice Rolling Tool (d4, d6, d8, d10, d12, d20, d100)
3. Rules Knowledge Base Tool (RAG with ChromaDB / 5e basic rules)
4. Character Management Tool (TinyDB persistence)
5. Interactive Web Interface (HTML5/CSS3/Vanilla JS) + REST API endpoints
"""

import os
import asyncio
import uuid
import random
import logging
from dataclasses import dataclass, asdict
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
import uvicorn
from tinydb import TinyDB, Query

from strands import Agent, tool

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

app = FastAPI(
    title="Once Upon Agentic AI - Game Master API & Web UI",
    description="Multi-Agent RPG Game Master with Dice Rolling, D&D Rules RAG, and Character Management",
    version="1.0.0",
)

# ---------------------------------------------------------
# Character Schema & Persistence (TinyDB)
# ---------------------------------------------------------
@dataclass
class Stats:
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10

@dataclass
class Character:
    character_id: str
    name: str
    character_class: str
    race: str
    gender: str
    stats: Stats

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DB_DIR, exist_ok=True)
characters_db = TinyDB(os.path.join(DB_DIR, "characters.json"))

# Seed sample character if empty
if not characters_db.all():
    default_char = Character(
        character_id="default-valeros-001",
        name="Valeros",
        character_class="Fighter",
        race="Human",
        gender="Male",
        stats=Stats(strength=16, dexterity=14, constitution=15, intelligence=10, wisdom=12, charisma=11),
    )
    characters_db.insert(asdict(default_char))

# ---------------------------------------------------------
# ChromaDB Rules RAG (Lazy Loader)
# ---------------------------------------------------------
_rules_collection = None

def get_rules_collection():
    global _rules_collection
    if _rules_collection is None:
        try:
            import chromadb
            possible_paths = [
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "5_a2a_integration", "utils", "rules_knowledge_base"),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules_knowledge_base"),
            ]
            for p in possible_paths:
                if os.path.exists(p):
                    client = chromadb.PersistentClient(path=p)
                    _rules_collection = client.get_or_create_collection(name="dnd_rules")
                    logging.info("Connected to ChromaDB rules collection at %s", p)
                    break
        except Exception as e:
            logging.warning("ChromaDB unavailable, using fallback rules: %s", e)
    return _rules_collection

# ---------------------------------------------------------
# Agent Tools
# ---------------------------------------------------------
@tool
def roll_dice(faces: int) -> int:
    """Roll a single polyhedral die with the given number of faces.

    Args:
        faces: Number of faces on the die (e.g. 4, 6, 8, 10, 12, 20, 100).

    Returns:
        An integer between 1 and faces, inclusive.
    """
    if faces < 1:
        raise ValueError("Dice must have at least 1 face")
    result = random.randint(1, faces)
    logging.info("🎲 DICE ROLL: d%s = %s", faces, result)
    return result

@tool
def query_rules(query: str) -> str:
    """Look up a rule in the official D&D Basic Rules knowledge base.

    Args:
        query: The rules question or topic in plain English (e.g. 'dexterity check', 'opportunity attack').

    Returns:
        The matching rules passages with page references.
    """
    col = get_rules_collection()
    if col is None:
        return "Rules knowledge base: Standard 5e rules apply. Ability checks add ability modifier; DC 10 is Easy, DC 15 is Medium, DC 20 is Hard."
    try:
        results = col.query(query_texts=[query], n_results=3)
        if not results or not results["documents"]:
            return "No specific rule passages found."
        return "\n\n".join(
            f"[Page {meta.get('page', '?')}] {doc}"
            for doc, meta in zip(results["documents"][0], results["metadatas"][0])
        )
    except Exception as e:
        return f"Standard 5e rules apply for '{query}'."

@tool
def find_character_by_name(name: str) -> dict:
    """Find a stored character by its exact name.

    Args:
        name: The character's name exactly as created.

    Returns:
        The character record as a dict.
    """
    records = characters_db.all()
    matches = [c for c in records if c.get("name", "").lower() == name.lower()]
    if not matches:
        raise ValueError(f"Character with name '{name}' not found")
    return matches[0]

@tool
def list_all_characters() -> list[dict]:
    """List every character stored in the database.

    Returns:
        A list of all character records.
    """
    return characters_db.all()

@tool
def create_character(name: str, character_class: str, race: str, gender: str, stats_dict: dict[str, int]) -> dict:
    """Create a new character and save it to the database.

    Args:
        name: The character's name.
        character_class: Class such as 'Fighter', 'Wizard', 'Rogue', 'Cleric'.
        race: Race such as 'Human', 'Elf', 'Dwarf'.
        gender: Character gender.
        stats_dict: Ability scores dict (strength, dexterity, constitution, intelligence, wisdom, charisma).

    Returns:
        The newly created character record.
    """
    char_id = str(uuid.uuid4())
    stats = Stats(
        strength=stats_dict.get("strength", 10),
        dexterity=stats_dict.get("dexterity", 10),
        constitution=stats_dict.get("constitution", 10),
        intelligence=stats_dict.get("intelligence", 10),
        wisdom=stats_dict.get("wisdom", 10),
        charisma=stats_dict.get("charisma", 10),
    )
    char = Character(
        character_id=char_id,
        name=name,
        character_class=character_class,
        race=race,
        gender=gender,
        stats=stats,
    )
    record = asdict(char)
    characters_db.insert(record)
    logging.info("✅ Created character %s (%s %s)", name, character_class, race)
    return record

# ---------------------------------------------------------
# Pydantic Structured Output Models
# ---------------------------------------------------------
class DiceOutput(BaseModel):
    dice_type: str = Field(description="The dice type, e.g. d4, d6, d20")
    result: int = Field(description="The numeric result of the roll")
    reason: str = Field(description="The reason for the roll and any modifiers applied")

class StoryOutput(BaseModel):
    response: str = Field(description="Your narrative response as the Game Master")
    actions_suggestions: list[str] = Field(description="List of 2-3 suggested actions for the player")
    details: str = Field(description="Brief summary of tools/rules used")
    dice_rolls: list[DiceOutput] = Field(default=[], description="List of dice rolls made during this turn")

class QuestionRequest(BaseModel):
    question: str

# ---------------------------------------------------------
# Game Master Agent & Fallback
# ---------------------------------------------------------
SYSTEM_PROMPT = """You are a Game Master for an epic fantasy role-playing game.
- Use `roll_dice` whenever random rolls, checks, or stats are needed. Always announce dice results with flair.
- Use `query_rules` to look up accurate 5e rules and cite page numbers.
- Use `create_character`, `find_character_by_name`, and `list_all_characters` for character management.
- Always narrate with theatrical flair and provide immersive fantasy role-playing adventure.
- Never make up information that a tool can tell you."""

agent = None
try:
    agent = Agent(
        system_prompt=SYSTEM_PROMPT,
        tools=[roll_dice, query_rules, find_character_by_name, list_all_characters, create_character],
        structured_output_model=StoryOutput,
    )
    logging.info("Agent initialized with BedrockModel default")
except Exception as e:
    logging.warning("Agent initialization warning: %s", e)

def fallback_game_master(question: str) -> dict:
    """Intelligent rule-based fallback when no cloud LLM credentials are configured."""
    q = question.lower()
    dice_rolls = []
    
    if "d20" in q or "roll" in q or "attack" in q or "check" in q:
        roll = roll_dice(20)
        dice_rolls.append({"dice_type": "d20", "result": roll, "reason": "Action check"})
        if roll == 20:
            narrative = f"🎲 Natural 20! A legendary critical strike! Your attack lands with devastating precision, shattering the enemy's guard."
        elif roll >= 12:
            narrative = f"🎲 You rolled a {roll}! You succeed in your action with graceful agility."
        else:
            narrative = f"🎲 You rolled a {roll}. The enemy parries your blow with a cruel sneer. You must reposition quickly!"
    elif "character" in q or "valeros" in q or "stats" in q:
        chars = list_all_characters()
        char_names = ", ".join(c.get("name", "Unknown") for c in chars)
        narrative = f"The tavern bustles as adventurers gather around the hearth. Currently registered heroes: {char_names}."
    else:
        roll = roll_dice(20)
        dice_rolls.append({"dice_type": "d20", "result": roll, "reason": "Perception check"})
        narrative = f"The torches flicker along the damp stone dungeon corridor. You sense shadows shifting ahead. (Perception check: {roll}). What do you choose to do next?"

    return {
        "response": narrative,
        "actions_suggestions": [
            "Draw your weapon and advance cautiously",
            "Cast a spell to illuminate the darkness",
            "Search for hidden traps or secret doors",
        ],
        "details": "Processed by local RPG engine (Connect AWS Bedrock or Gemini API keys in Render settings for full Claude Sonnet multi-agent reasoning)",
        "dice_rolls": dice_rolls,
    }

# ---------------------------------------------------------
# Embedded Web UI (HTML5 / Modern Dark RPG Theme)
# ---------------------------------------------------------
HTML_UI = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Once Upon Agentic AI | Multi-Agent RPG Game Master</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700;900&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0b0f19;
      --card-bg: #141b2d;
      --border: #232f4e;
      --accent: #d4af37;
      --accent-glow: rgba(212, 175, 55, 0.25);
      --text: #e2e8f0;
      --text-muted: #94a3b8;
      --cyan: #38bdf8;
      --green: #22c55e;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg);
      color: var(--text);
      font-family: 'Inter', sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }
    header {
      background: linear-gradient(180deg, #141c2f 0%, #0b0f19 100%);
      border-bottom: 1px solid var(--border);
      padding: 1.25rem 2rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      box-shadow: 0 4px 20px rgba(0,0,0,0.5);
    }
    .logo-group { display: flex; align-items: center; gap: 0.75rem; }
    .logo-icon { font-size: 2rem; }
    h1 {
      font-family: 'Cinzel', serif;
      font-size: 1.5rem;
      color: var(--accent);
      letter-spacing: 1px;
      text-shadow: 0 0 12px var(--accent-glow);
    }
    .subtitle { font-size: 0.8rem; color: var(--text-muted); }
    .status-badge {
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      background: rgba(34, 197, 94, 0.1);
      border: 1px solid rgba(34, 197, 94, 0.3);
      color: var(--green);
      padding: 0.35rem 0.75rem;
      border-radius: 9999px;
      font-size: 0.8rem;
      font-weight: 600;
    }
    .status-dot { width: 8px; height: 8px; background: var(--green); border-radius: 50%; box-shadow: 0 0 8px var(--green); }
    .container {
      max-width: 1200px;
      width: 100%;
      margin: 0 auto;
      padding: 1.5rem;
      display: grid;
      grid-template-columns: 320px 1fr;
      gap: 1.5rem;
      flex: 1;
    }
    .sidebar { display: flex; flex-direction: column; gap: 1.25rem; }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.25rem;
      box-shadow: 0 8px 24px rgba(0,0,0,0.3);
    }
    .card-title {
      font-family: 'Cinzel', serif;
      font-size: 1rem;
      color: var(--accent);
      margin-bottom: 0.85rem;
      display: flex;
      align-items: center;
      gap: 0.5rem;
      border-bottom: 1px solid var(--border);
      padding-bottom: 0.5rem;
    }
    .dice-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 0.5rem;
    }
    .dice-btn {
      background: #1e293b;
      border: 1px solid var(--border);
      color: var(--text);
      padding: 0.6rem 0.2rem;
      border-radius: 8px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s ease;
      font-size: 0.85rem;
    }
    .dice-btn:hover {
      background: var(--accent);
      color: #0b0f19;
      transform: translateY(-2px);
      box-shadow: 0 4px 12px var(--accent-glow);
    }
    .char-info { font-size: 0.85rem; line-height: 1.6; color: var(--text-muted); }
    .char-info strong { color: var(--text); }
    .stat-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.4rem; margin-top: 0.5rem; text-align: center; }
    .stat-box { background: #0f172a; padding: 0.4rem; border-radius: 6px; border: 1px solid var(--border); }
    .stat-box .val { font-size: 1.1rem; font-weight: 700; color: var(--accent); }
    .stat-box .lbl { font-size: 0.65rem; color: var(--text-muted); text-transform: uppercase; }
    .main-chat {
      display: flex;
      flex-direction: column;
      height: 75vh;
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 8px 24px rgba(0,0,0,0.3);
    }
    .chat-messages {
      flex: 1;
      padding: 1.5rem;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }
    .msg {
      max-width: 85%;
      padding: 1rem 1.25rem;
      border-radius: 10px;
      line-height: 1.5;
      font-size: 0.95rem;
      animation: fadeIn 0.3s ease;
    }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
    .msg-user {
      align-self: flex-end;
      background: #1e3a8a;
      border: 1px solid #3b82f6;
      color: #fff;
    }
    .msg-gm {
      align-self: flex-start;
      background: #0f172a;
      border: 1px solid var(--border);
      border-left: 4px solid var(--accent);
    }
    .msg-gm-author {
      font-family: 'Cinzel', serif;
      font-size: 0.8rem;
      color: var(--accent);
      margin-bottom: 0.4rem;
      display: flex;
      align-items: center;
      gap: 0.4rem;
    }
    .dice-tag {
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      background: rgba(212, 175, 55, 0.15);
      border: 1px solid var(--accent);
      color: var(--accent);
      padding: 0.2rem 0.5rem;
      border-radius: 6px;
      font-size: 0.75rem;
      font-weight: 700;
      margin: 0.4rem 0.25rem 0 0;
    }
    .suggestions {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      margin-top: 0.75rem;
      padding-top: 0.5rem;
      border-top: 1px solid rgba(255,255,255,0.08);
    }
    .sugg-btn {
      background: rgba(56, 189, 248, 0.1);
      border: 1px solid rgba(56, 189, 248, 0.3);
      color: var(--cyan);
      padding: 0.35rem 0.7rem;
      border-radius: 6px;
      font-size: 0.75rem;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .sugg-btn:hover {
      background: var(--cyan);
      color: #0b0f19;
      font-weight: 600;
    }
    .chat-input-bar {
      padding: 1rem 1.5rem;
      background: #0d1322;
      border-top: 1px solid var(--border);
      display: flex;
      gap: 0.75rem;
    }
    .chat-input {
      flex: 1;
      background: #141b2d;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 0.75rem 1rem;
      color: var(--text);
      font-size: 0.95rem;
      outline: none;
    }
    .chat-input:focus { border-color: var(--accent); box-shadow: 0 0 10px var(--accent-glow); }
    .send-btn {
      background: var(--accent);
      color: #0b0f19;
      font-weight: 700;
      border: none;
      border-radius: 8px;
      padding: 0 1.5rem;
      cursor: pointer;
      transition: all 0.2s ease;
      font-family: 'Cinzel', serif;
    }
    .send-btn:hover { background: #facc15; transform: translateY(-1px); }
    @media (max-width: 860px) {
      .container { grid-template-columns: 1fr; }
      .sidebar { order: 2; }
      .main-chat { height: 60vh; order: 1; }
    }
  </style>
</head>
<body>
  <header>
    <div class="logo-group">
      <div class="logo-icon">🐉</div>
      <div>
        <h1>Once Upon Agentic AI</h1>
        <div class="subtitle">Autonomous Multi-Agent Fantasy RPG Orchestrator</div>
      </div>
    </div>
    <div class="status-badge">
      <div class="status-dot"></div>
      <span>Game Master Live</span>
    </div>
  </header>

  <div class="container">
    <aside class="sidebar">
      <div class="card">
        <div class="card-title">🎲 Polyhedral Dice</div>
        <div class="dice-grid">
          <button class="dice-btn" onclick="quickRoll(4)">d4</button>
          <button class="dice-btn" onclick="quickRoll(6)">d6</button>
          <button class="dice-btn" onclick="quickRoll(8)">d8</button>
          <button class="dice-btn" onclick="quickRoll(10)">d10</button>
          <button class="dice-btn" onclick="quickRoll(12)">d12</button>
          <button class="dice-btn" onclick="quickRoll(20)" style="border-color: var(--accent); color: var(--accent);">d20</button>
          <button class="dice-btn" onclick="quickRoll(100)">d100</button>
        </div>
      </div>

      <div class="card">
        <div class="card-title">🛡️ Active Adventurer</div>
        <div class="char-info" id="char-panel">
          <div><strong>Name:</strong> Valeros</div>
          <div><strong>Class:</strong> Fighter (Human, Male)</div>
          <div class="stat-row">
            <div class="stat-box"><div class="val">16</div><div class="lbl">STR</div></div>
            <div class="stat-box"><div class="val">14</div><div class="lbl">DEX</div></div>
            <div class="stat-box"><div class="val">15</div><div class="lbl">CON</div></div>
            <div class="stat-box"><div class="val">10</div><div class="lbl">INT</div></div>
            <div class="stat-box"><div class="val">12</div><div class="lbl">WIS</div></div>
            <div class="stat-box"><div class="val">11</div><div class="lbl">CHA</div></div>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-title">📜 System Information</div>
        <div class="char-info" style="font-size: 0.8rem;">
          <div>• <strong>Framework:</strong> Strands Agents SDK</div>
          <div>• <strong>Protocols:</strong> A2A + Model Context Protocol</div>
          <div>• <strong>RAG:</strong> ChromaDB Vector Database</div>
          <div>• <strong>State:</strong> In-process TinyDB</div>
          <div>• <strong>API Docs:</strong> <a href="/docs" target="_blank" style="color: var(--cyan); text-decoration: none;">Interactive Swagger /docs</a></div>
        </div>
      </div>
    </aside>

    <main class="main-chat">
      <div class="chat-messages" id="messages">
        <div class="msg msg-gm">
          <div class="msg-gm-author">🎭 Game Master</div>
          <div>Welcome, brave adventurer. You stand before the moss-covered gates of the Sunken Citadel. The cold mountain wind howls across the craggy canyon, carrying faint echoes of goblin drums from deep below. How do you wish to proceed?</div>
          <div class="suggestions">
            <button class="sugg-btn" onclick="sendAction('I draw my longsword and inspect the dungeon gate for traps.')">🔍 Inspect gate for traps</button>
            <button class="sugg-btn" onclick="sendAction('I roll a d20 dexterity check to quietly climb the crumbled parapet.')">🎲 Roll Dexterity Check</button>
            <button class="sugg-btn" onclick="sendAction('What do the D&D basic rules say about darkvision and illumination?')">📜 Query 5e Rules</button>
          </div>
        </div>
      </div>

      <form class="chat-input-bar" onsubmit="handleSubmit(event)">
        <input type="text" id="userInput" class="chat-input" placeholder="Declare your action, roll dice, or inquire about rules..." autocomplete="off">
        <button type="submit" class="send-btn" id="sendBtn">Inquire</button>
      </form>
    </main>
  </div>

  <script>
    const messagesEl = document.getElementById('messages');
    const inputEl = document.getElementById('userInput');
    const sendBtn = document.getElementById('sendBtn');

    function appendMessage(text, isUser, diceRolls = [], suggestions = [], details = '') {
      const msg = document.createElement('div');
      msg.className = 'msg ' + (isUser ? 'msg-user' : 'msg-gm');
      
      if (!isUser) {
        let diceHtml = '';
        if (diceRolls && diceRolls.length > 0) {
          diceHtml = diceRolls.map(d => `<span class="dice-tag">🎲 ${d.dice_type}: ${d.result} (${d.reason || ''})</span>`).join('');
        }
        let suggHtml = '';
        if (suggestions && suggestions.length > 0) {
          suggHtml = '<div class="suggestions">' + suggestions.map(s => `<button class="sugg-btn" onclick="sendAction('${s.replace(/'/g, "\\\\'")}')">${s}</button>`).join('') + '</div>';
        }
        let detHtml = details ? `<div style="font-size:0.7rem; color: #64748b; margin-top:0.4rem;">⚙️ ${details}</div>` : '';

        msg.innerHTML = `
          <div class="msg-gm-author">🎭 Game Master</div>
          <div>${text}</div>
          ${diceHtml ? `<div>${diceHtml}</div>` : ''}
          ${detHtml}
          ${suggHtml}
        `;
      } else {
        msg.textContent = text;
      }
      
      messagesEl.appendChild(msg);
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    async function sendAction(text) {
      if (!text || !text.trim()) return;
      appendMessage(text, true);
      inputEl.value = '';
      sendBtn.disabled = true;
      sendBtn.textContent = 'Thinking...';

      try {
        const res = await fetch('/inquire', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: text })
        });
        const data = await res.json();
        if (data.response) {
          const resp = data.response;
          appendMessage(
            resp.response || resp,
            false,
            resp.dice_rolls || [],
            resp.actions_suggestions || [],
            resp.details || ''
          );
        } else if (data.error) {
          appendMessage('⚠️ Error: ' + data.error, false);
        }
      } catch (err) {
        appendMessage('⚠️ Network Error: ' + err.message, false);
      } finally {
        sendBtn.disabled = false;
        sendBtn.textContent = 'Inquire';
      }
    }

    function handleSubmit(e) {
      e.preventDefault();
      sendAction(inputEl.value);
    }

    function quickRoll(faces) {
      sendAction(`I roll a d${faces}!`);
    }
  </script>
</body>
</html>
"""

# ---------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def index():
    """Serves the interactive Game Master web interface."""
    return HTMLResponse(content=HTML_UI)

@app.get("/health")
def health():
    return {"status": "healthy", "service": "game-master-api", "characters_count": len(characters_db.all())}

@app.get("/messages")
def get_messages():
    if agent and hasattr(agent, "messages"):
        return agent.messages
    return []

@app.get("/user/{user_name}")
def get_user(user_name: str):
    Character_Query = Query()
    result = characters_db.search(Character_Query.name == user_name)
    if not result:
        return JSONResponse(status_code=404, content={"error": f"Character '{user_name}' not found"})
    return result[0]

@app.post("/inquire")
async def inquire(request: QuestionRequest):
    logging.info("Processing inquiry: %s", request.question)
    # Attempt cloud agent execution if configured
    if agent is not None:
        try:
            response = await asyncio.wait_for(agent.invoke_async(request.question), timeout=12.0)
            if hasattr(response, "structured_output") and response.structured_output:
                output = response.structured_output.model_dump()
                return JSONResponse(content={"response": output})
            return JSONResponse(content={"response": {"response": str(response), "actions_suggestions": [], "dice_rolls": []}})
        except Exception as e:
            logging.warning("Cloud agent invocation error, falling back to local RPG engine: %s", e)
    
    # Graceful fallback response
    fallback = fallback_game_master(request.question)
    return JSONResponse(content={"response": fallback})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8009))
    logging.info("Starting standalone Game Master API & Web UI on port %s", port)
    uvicorn.run(app, host="0.0.0.0", port=port)
