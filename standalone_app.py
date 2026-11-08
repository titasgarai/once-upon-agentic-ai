"""Standalone Game Master API for Free Cloud Deployment (Render, Hugging Face, Railway).

Bundles the Game Master orchestrator, the dice rolling tool, the rules knowledge base,
and character management into a single production-ready FastAPI service.
"""

import os
import uuid
import random
import logging
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Optional

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from tinydb import TinyDB, Query
import chromadb

from strands import Agent, tool

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ---------------------------------------------------------
# App Initialization & CORS
# ---------------------------------------------------------
app = FastAPI(title="Once Upon Agentic AI - Game Master API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_private_network=True,
)

# ---------------------------------------------------------
# Local Storage: Characters (TinyDB) & Rules (ChromaDB)
# ---------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHARACTERS_DB_PATH = os.path.join(BASE_DIR, "characters.json")
characters_db = TinyDB(CHARACTERS_DB_PATH, indent=4, separators=(",", ": "))

RULES_KB_PATH = os.path.join(BASE_DIR, "5_a2a_integration", "utils", "rules_knowledge_base")
_chroma_collection = None

def get_rules_collection():
    global _chroma_collection
    if _chroma_collection is None:
        if os.path.exists(RULES_KB_PATH):
            _chroma_collection = chromadb.PersistentClient(path=RULES_KB_PATH).get_collection("basic_rules")
        else:
            logging.warning("Rules knowledge base not found at %s. Running without local RAG index.", RULES_KB_PATH)
    return _chroma_collection

# ---------------------------------------------------------
# Character Data Model
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
class InventoryItem:
    item_name: str
    quantity: int

@dataclass
class Character:
    character_id: str
    name: str
    character_class: str
    race: str
    gender: str
    level: int = 1
    experience: int = 0
    stats: Stats = None
    inventory: list[InventoryItem] = None
    created_at: str = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.stats is None:
            self.stats = Stats()
        if self.inventory is None:
            self.inventory = [
                InventoryItem("Starting Equipment Pack", 1),
                InventoryItem("Gold Pieces", 100),
            ]

# ---------------------------------------------------------
# Agent Tools
# ---------------------------------------------------------
@tool
def roll_dice(faces: int = 6) -> int:
    """Roll one die with a given number of faces and return the result.

    Args:
        faces: Number of faces on the die (e.g. 4, 6, 8, 10, 12, 20, 100). Defaults to 6.

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
        return "Rules knowledge base is not installed locally. Refer to standard 5e rules."
    results = col.query(query_texts=[query], n_results=3)
    if not results or not results["documents"]:
        return "No specific rule passages found."
    return "\n\n".join(
        f"[Page {meta.get('page', '?')}] {doc}"
        for doc, meta in zip(results["documents"][0], results["metadatas"][0])
    )

@tool
def find_character_by_name(name: str) -> dict:
    """Find a stored character by its exact name.

    Args:
        name: The character's name exactly as created.

    Returns:
        The character record as a dict.
    """
    records = characters_db.all()
    matches = [c for c in records if c.get("name") == name]
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
# Game Master Agent
# ---------------------------------------------------------
SYSTEM_PROMPT = """You are a Game Master for an epic fantasy role-playing game.
- Use `roll_dice` whenever random rolls, checks, or stats are needed. Always announce dice results with flair.
- Use `query_rules` to look up accurate 5e rules and cite page numbers.
- Use `create_character`, `find_character_by_name`, and `list_all_characters` for character management.
- Always narrate with theatrical flair and provide immersive fantasy role-playing adventure.
- Never make up information that a tool can tell you."""

agent = Agent(
    system_prompt=SYSTEM_PROMPT,
    tools=[roll_dice, query_rules, find_character_by_name, list_all_characters, create_character],
    structured_output_model=StoryOutput,
)

# ---------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------
@app.get("/")
@app.get("/health")
def health():
    return {"status": "healthy", "service": "game-master-api"}

@app.get("/messages")
def get_messages():
    return agent.messages

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
    try:
        response = await agent.invoke_async(request.question)
        output = response.structured_output.model_dump()
        return JSONResponse(content={"response": output})
    except Exception as e:
        logging.error("Inquiry error: %s", str(e), exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8009))
    logging.info("Starting standalone Game Master API on port %s", port)
    uvicorn.run(app, host="0.0.0.0", port=port)

