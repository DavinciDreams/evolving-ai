# Evolving AI Agent - Web GUI

A modern React web interface for the Evolving AI Agent system, built with Vite, React 18, Tailwind CSS, and React Query.

## Features

- **Chat Interface** - Real-time conversations with the AI agent, markdown support, code highlighting, and evaluation scores
- **Memory Browser** - Search and explore stored memories with timestamps and metadata
- **Knowledge Base** - Browse knowledge entries organized by categories with confidence scores
- **GitHub Integration** - Monitor PRs, commits, and trigger code improvements
- **Analytics Dashboard** - View system metrics, interaction counts, and agent status

## Getting Started

### Running the Application

**Terminal 1 - Start Backend:**
```bash
cd /home/ubuntu/evolving-ai
python -m uvicorn api_server:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2 - Start Frontend:**
```bash
cd /home/ubuntu/evolving-ai/frontend
npm run dev
```

Then open your browser to http://localhost:3001 (or the port shown in the terminal).

## Project Structure

All code is in the `frontend/` directory with a clean component-based architecture.

For detailed documentation, see [frontend/README.md](frontend/README.md)
