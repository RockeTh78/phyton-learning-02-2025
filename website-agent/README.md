# Website Generator Agent

An autonomous agent that reads a `requirements.yaml` file and generates a complete
Flask web application, runs local tests, and prepares it for Railway deployment.

## How it works

1. **Reads** your `requirements.yaml` (topic, features, colors, etc.)
2. **Generates** a full Flask app from scratch in `output/<project_name>/`
3. **Tests** it locally (installs deps, starts Flask, hits endpoints)
4. **Creates** a GitHub repo and pushes the code (`gh` CLI)
5. **Deploys** to Railway and sets all environment variables (`railway` CLI)
6. **Reports** the live URL and any remaining steps

## Prerequisites

```bash
pip install anthropic pyyaml requests
```

Three CLIs must be installed and authenticated:

```bash
# 1. Anthropic API key
export ANTHROPIC_API_KEY=sk-ant-...

# 2. GitHub CLI — https://cli.github.com
brew install gh
gh auth login

# 3. Railway CLI — https://docs.railway.app/guides/cli
brew install railway
railway login
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
  github_user: "RockeTh78"    # your GitHub username
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

## Deployment

The agent handles everything automatically:
- Creates a public GitHub repo under your `github_user`
- Pushes the generated code
- Runs `railway init`, sets all env vars, runs `railway up`
- Returns the live Railway URL

The only thing you may need to add manually is a **Railway Volume** at `/data`
(Railway CLI v4 supports `railway volume add --mount /data`, but dashboard is faster).

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
