# Website Generator Agent

An autonomous agent that reads a `requirements.yaml` file and generates a complete
Flask web application, runs local tests, and prepares it for Railway deployment.

## How it works

1. **Reads** your `requirements.yaml` (topic, features, colors, etc.)
2. **Studies** the reference travel blog at `../travel-blog/` to understand the patterns
3. **Generates** a full Flask app adapted to your requirements in `output/<project_name>/`
4. **Tests** it locally (installs deps, starts Flask, hits endpoints)
5. **Sets up git** (init + initial commit)
6. **Reports** what was created and any remaining steps

## Prerequisites

```bash
pip install anthropic pyyaml requests
```

You need an `ANTHROPIC_API_KEY` in your environment:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

## Quick Start

```bash
cd website-agent

# Run with the example recipe blog requirements
python agent.py requirements_example.yaml

# Or point to your own requirements file
python agent.py path/to/my_requirements.yaml
```

The generated project lands in:
```
website-agent/output/<project_name>/
```

## Writing your own requirements.yaml

```yaml
project_name: "my-fitness-blog"       # used as output directory name
topic: "Fitness Blog"                  # short label shown to the agent
description: "A blog for workout logs and AI-generated fitness tips from gym photos"
language: "en"                         # primary language for content

features:
  - "AI-generated workout descriptions from photos"
  - "Multi-language EN/DE/FR"
  - "Login protection for uploads"
  - "Affiliate links to fitness gear (Amazon)"
  - "Mobile-optimized"

style:
  primary_color: "#2b9348"             # CSS hex color
  theme: "energetic, clean, minimal"   # passed to agent for CSS inspiration
  font: "Inter, sans-serif"            # optional override

deployment:
  platform: "railway"
  port: 8080
```

## Generated file structure

```
output/<project_name>/
  app.py                  # Flask application
  content_generator.py    # Anthropic Claude AI integration
  affiliate.py            # Affiliate link generator
  requirements.txt        # Python deps
  Procfile                # gunicorn start command
  railway.toml            # Railway deploy config
  nixpacks.toml           # Build config (python + ffmpeg)
  .env.example            # Required env vars
  .gitignore
  templates/
    base.html             # Base layout with i18n JS
    index.html            # Post listing
    post.html             # Single post view
    upload.html           # Upload form
    login.html            # Login page
  static/
    style.css             # Full responsive CSS
```

## Deploying to Railway

1. Create a new Railway project and link a GitHub repo
2. Push the generated project to that repo
3. Add a **Volume** mounted at `/data`
4. Set these environment variables in Railway:
   - `ANTHROPIC_API_KEY` — your Anthropic key
   - `BLOG_PASSWORD` — login password
   - `SECRET_KEY` — Flask session secret (random string)
   - `STORAGE_PATH` — `/data` (matches Railway volume)
   - Any affiliate IDs from `.env.example`
5. Railway will auto-deploy on push

## Architecture

```
agent.py          Agentic loop: calls Claude claude-opus-4-5, processes tool use
tools.py          Tool implementations (create_file, read_file, run_command, …)
requirements_example.yaml   Example input
output/           Generated projects land here
```

The agent uses Claude `claude-opus-4-5` (or `claude-opus-4-6` when available) with a
tool-use loop. It keeps iterating until `stop_reason == "end_turn"`, processing all
tool calls at each step and feeding results back into the conversation.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ANTHROPIC_API_KEY` not set | `export ANTHROPIC_API_KEY=sk-ant-...` |
| Port 8080 already in use during test | `lsof -ti:8080 \| xargs kill` |
| Agent hits max iterations (60) | Re-run; the agent starts fresh each time |
| Generated app won't start | Check `output/<name>/app.py` for import errors |
