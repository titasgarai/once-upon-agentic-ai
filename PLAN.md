# Project Plan & Delivery Roadmap: Once Upon Agentic AI

## Project Overview
This plan outlines the progression of the **Once Upon Agentic AI** platform from local prototype exercises to an integrated multi-agent architecture and a free, production-ready cloud deployment.

---

## Phase 1: Local Foundation & Core Agent Summoning (Completed)

- [x] **Environment Configuration:**
  - Installed `uv` package manager and Python 3.13.5 virtual environment.
  - Resolved and synchronized all 167 dependencies.
  - Verified AWS STS credentials and region configuration.
- [x] **Chapter 1: Agent Summoning (`1_strands_basics`):**
  - Initialized foundational `Agent` instance with system persona.
  - Configured granular debug logging to inspect Bedrock API streaming events.
- [x] **Chapter 2: Vended Tools (`2_vended_tools`):**
  - Integrated `http_request` tool querying the live Open5e REST API for spells and monsters.
- [x] **Chapter 3: Custom Tool Forging (`3_custom_tools`):**
  - Authored `@tool roll_dice` supporting arbitrary faces and automatic JSON schema generation.
  - Verified 4d6-drop-lowest ability score generation.

---

## Phase 2: Distributed Protocols & Multi-Agent Orchestration (Completed)

- [x] **Chapter 4: Model Context Protocol (`4_mcp_integration`):**
  - Created standalone FastMCP server over `streamable-http` (port 8002).
  - Wired `MCPClient` into the Game Master agent.
- [x] **Chapter 5: Agent-to-Agent Protocol (`5_a2a_integration`):**
  - Ingested official D&D Basic Rules into ChromaDB vector database (979 passages).
  - Built **Rules Agent A2A Server** (port 8000) for page-referenced semantic search.
  - Built **Character Agent A2A Server** (port 8001) with TinyDB persistence.
  - Built **Game Master Orchestrator** (port 8009) with Pydantic `StoryOutput` structured responses.
- [x] **Chapter 7 & 8: Harness & Production Design:**
  - Explored Strands Harness with unified session contracts.
  - Authored AgentCore cloud configuration with SigV4 authentication, managed memory, and knowledge base policies.

---

## Phase 3: Project Cleanup & Repository Presentation (Current Phase)

- [x] **Remove Temporary / Unused Scaffolding:**
  - Cleaned redundant CLI scaffolding and temporary test folders (`gameprod`).
  - Verified `.gitignore` prevents secrets, `.env`, `.venv`, and temporary caches from entering git.
- [x] **Presentation Documentation:**
  - Created [`CONTEXT.md`](CONTEXT.md) describing system architecture, data models, and protocols.
  - Created [`PLAN.md`](PLAN.md) detailing roadmap and milestones.
  - Created comprehensive [`README.md`](README.md) featuring setup, diagrams, and deployment guides.
- [x] **Unified Deployment Entrypoint:**
  - Created [`standalone_app.py`](standalone_app.py) for single-port / single-container free cloud environments.
  - Created [`requirements.txt`](requirements.txt) for standard pip-based cloud builders.

---

## Phase 4: GitHub Publication & Free Cloud Deployment (Next Steps)

### Milestone 4.1: Push to GitHub
1. Initialize local git repository in `sample-once-upon-agentic-ai`.
2. Stage and commit all clean, structured files.
3. Link to user's remote GitHub repository and push to `main`.

### Milestone 4.2: Free Backend Deployment (Render.com)
1. Link GitHub repository to Render as a Free Web Service.
2. Build command: `pip install -r requirements.txt`.
3. Start command: `python standalone_app.py`.
4. Configure environment variables (AWS credentials or free Gemini/Groq model API key).

### Milestone 4.3: Free Frontend Web UI (GitHub Pages)
1. Publish the static HTML/JS frontend to GitHub Pages.
2. Configure UI endpoint to point to the live Render HTTPS backend URL.

---

## Phase 5: Future Enhancements

- [ ] **Multi-Model Support:** Add automatic fallback across Google Gemini, Anthropic Claude, and Groq Llama 3.
- [ ] **Multiplayer Party Mode:** Extend session management to support multiple players in the same campaign room.
- [ ] **AI Battle Map Generation:** Integrate an image generation tool (e.g. Amazon Titan Image Generator / Flux) to produce visual encounter maps.

