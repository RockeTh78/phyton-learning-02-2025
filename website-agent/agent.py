#!/usr/bin/env python3
"""
Autonomous Website Generator Agent
====================================
Reads a requirements.yaml, uses the travel-blog as a reference implementation,
and autonomously creates a complete Flask web application via Claude tool-use.

Usage:
    python agent.py requirements_example.yaml
    python agent.py path/to/my_requirements.yaml
"""

import json
import sys
import textwrap
import time
from pathlib import Path

import anthropic
import yaml

from tools import execute_tool

# ─── Paths ────────────────────────────────────────────────────────────────────

AGENT_DIR = Path(__file__).parent.resolve()
OUTPUT_BASE = AGENT_DIR / "output"
REFERENCE_BLOG = Path("/Users/thomashoche/DEV/phyton-learning-02-2025/travel-blog")

# ─── Model ────────────────────────────────────────────────────────────────────

MODEL = "claude-opus-4-6"

# ─── Tool Schemas ─────────────────────────────────────────────────────────────

TOOLS: list[dict] = [
    {
        "name": "create_file",
        "description": (
            "Write a file to the output project directory. "
            "Creates parent directories automatically. "
            "Use this to generate all project files."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path inside the project, e.g. 'app.py' or 'templates/base.html'",
                },
                "content": {
                    "type": "string",
                    "description": "Full file content to write.",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "append_to_file",
        "description": "Append content to an existing file in the project directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path inside the project."},
                "content": {"type": "string", "description": "Content to append."},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "read_file",
        "description": (
            "Read a file from the REFERENCE travel blog at "
            "/Users/thomashoche/DEV/phyton-learning-02-2025/travel-blog/. "
            "Use relative paths like 'app.py', 'templates/base.html', 'static/style.css'. "
            "You can also pass an absolute path to read any other file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path in the reference blog, or absolute path.",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "run_command",
        "description": (
            "Execute a shell command. Returns combined stdout + stderr. "
            "Use for pip install, git commands, starting/stopping Flask, etc. "
            "Timeout: 120 s."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run."},
                "cwd": {
                    "type": "string",
                    "description": "Working directory (absolute path). Defaults to project output dir.",
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "test_endpoint",
        "description": (
            "HTTP GET a URL and return the status code plus first 500 chars of body. "
            "Use to verify Flask routes are working."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Full URL, e.g. 'http://localhost:8080/'"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "list_files",
        "description": (
            "List files recursively in a directory. "
            "Pass '.' or '' to list the project output root. "
            "Pass an absolute path to list any directory (e.g. the reference blog)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory to list. Relative paths are resolved inside the project dir.",
                },
            },
            "required": ["directory"],
        },
    },
    {
        "name": "check_domain",
        "description": (
            "Check if a domain name is available for registration via Cloudflare Registrar "
            "and return the price. Requires CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID env vars. "
            "Always call this before register_domain."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Full domain name, e.g. 'my-recipe-blog.de' or 'myapp.com'",
                },
            },
            "required": ["domain"],
        },
    },
    {
        "name": "confirm_with_user",
        "description": (
            "Show the user a summary message in the terminal and wait for them to type 'ja' or 'nein'. "
            "ALWAYS call this before register_domain. Include domain name, price, and what will happen. "
            "Only proceed with registration if this returns CONFIRMED."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": (
                        "Summary shown to the user. Include: domain name, price/year, "
                        "total for chosen years, and next steps (DNS setup, Railway linking)."
                    ),
                },
            },
            "required": ["message"],
        },
    },
    {
        "name": "register_domain",
        "description": (
            "Register a domain via Cloudflare Registrar API. "
            "ONLY call this after confirm_with_user returned CONFIRMED. "
            "The Cloudflare account must have a valid payment method on file. "
            "Requires CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Full domain name to register, e.g. 'my-recipe-blog.de'",
                },
                "years": {
                    "type": "integer",
                    "description": "Registration period in years (default: 1)",
                },
            },
            "required": ["domain"],
        },
    },
    {
        "name": "configure_dns",
        "description": (
            "Add a CNAME record to a Cloudflare-managed domain to point it at the Railway deployment. "
            "Cloudflare proxy (CDN + DDoS protection) is enabled automatically for CNAME records. "
            "Requires CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID. "
            "The domain must be registered/active in Cloudflare first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Root domain, e.g. 'my-recipe-blog.de'",
                },
                "host": {
                    "type": "string",
                    "description": "Subdomain: 'www' for www prefix, '@' for root domain",
                },
                "answer": {
                    "type": "string",
                    "description": "CNAME target, i.e. the Railway public URL, e.g. 'myapp.up.railway.app'",
                },
                "record_type": {
                    "type": "string",
                    "description": "DNS record type: 'CNAME' (default) or 'A'",
                },
            },
            "required": ["domain", "host", "answer"],
        },
    },
]

# ─── System Prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = textwrap.dedent("""
You are an expert Python / Flask developer and autonomous website generator agent.

Your task: read a requirements.yaml and generate a COMPLETE, production-ready
Flask web application from scratch — a genuinely NEW project tailored to the topic.

## TECHNICAL STACK (always use these)
- Flask + SQLite (via sqlite3, no ORM)
- Anthropic Claude API (claude-sonnet-4-6) for AI content generation
- Gunicorn as production WSGI server
- Railway for deployment (nixpacks builder, persistent volume)
- Vanilla JS + CSS (no frameworks)
- Session-based login with password from env var

## REFERENCE (for technical patterns only — do NOT copy code)
There is a reference Flask blog at:
  /Users/thomashoche/DEV/phyton-learning-02-2025/travel-blog/

You may read individual files to understand patterns (e.g. how Railway volume
paths work, how to structure the agentic loop, how SQLite migrations work,
how the Claude API is called with vision). But you must write ALL code fresh —
the new project must have its OWN design, its OWN database schema, its OWN
content model, and its OWN UI suited to the topic in requirements.yaml.

## YOUR WORKFLOW

### Step 1 — Understand the requirements
Read requirements.yaml carefully. Understand:
- What is the domain/topic?
- What content model fits? (e.g. recipes have ingredients + steps; a fitness blog has workouts + muscles)
- What does AI analysis of uploaded photos produce?
- What affiliate links are relevant?
- What languages?
- What visual theme?

If helpful, read ONE OR TWO reference files for a specific pattern
(e.g. railway.toml or nixpacks.toml to get the exact Railway config syntax).
Do NOT read all reference files — build from your own knowledge first.

### Step 2 — Design the data model
Decide on the SQLite schema tailored to the topic. For example:
- Recipe blog: id, title, ingredients (JSON), steps (JSON), cuisine, difficulty, prep_time, ...
- Fitness blog: id, title, exercise_type, muscles (JSON), duration, equipment, ...
Design it to fit the domain, not just "posts with content".

### Step 3 — Generate ALL project files from scratch
Create every file fresh. Required files:
  app.py               - Flask app with routes, DB, login
  content_generator.py - Claude API integration for this domain
  affiliate.py         - Affiliate links relevant to this topic
  requirements.txt     - flask, anthropic, Pillow, gunicorn, python-dotenv, requests
  Procfile             - web: gunicorn ...
  railway.toml         - Railway config
  nixpacks.toml        - [phases.setup] nixPkgs = ["python311", "ffmpeg"]
  .env.example         - ANTHROPIC_API_KEY, SECRET_KEY, BLOG_PASSWORD, STORAGE_PATH
  .gitignore           - standard Python + .env
  templates/base.html  - Full HTML with nav, i18n JS dict (all requested languages)
  templates/index.html - Listing page appropriate for the domain
  templates/post.html  - Detail page for one item
  templates/upload.html - Upload/create form
  templates/login.html - Simple login form
  static/style.css     - Fresh CSS matching the requested theme and colors

### Step 4 — Install & test locally
1. pip install -r requirements.txt
2. Start Flask: ANTHROPIC_API_KEY=dummy python app.py & sleep 3
3. test_endpoint http://localhost:8080/
4. test_endpoint http://localhost:8080/login
5. Kill Flask: pkill -f "python app.py" || true

### Step 5 — Git setup & GitHub push
1. git init
2. Create .gitignore
3. git add -A && git commit -m "Initial commit: <project_name>"
4. Create GitHub repo:
   gh repo create <github_user>/<repo_name> --public --source=. --remote=origin --push
   (repo_name = requirements.deployment.github_repo or project_name)
   If gh is not installed or not authenticated, report this clearly and skip.

### Step 6 — Railway deployment
After GitHub push succeeds, deploy via Railway CLI:
1. Check Railway CLI is available: railway --version
2. Link to new Railway project:
   railway init --name <project_name>
3. Set required environment variables one by one:
   railway variables set ANTHROPIC_API_KEY=<from local env or placeholder>
   railway variables set SECRET_KEY=<random 32-char hex string>
   railway variables set BLOG_PASSWORD=admin
   railway variables set STORAGE_PATH=/data
4. Add persistent volume (Railway CLI v4+):
   railway volume add --mount /data
   (If this command fails, note that the user must add the volume manually in the Railway dashboard)
5. Deploy:
   railway up --detach
6. Get the deployment URL:
   railway domain
   Then test_endpoint on the returned URL + /login

### Step 7 — Domain registration (if domain configured in requirements.yaml)
If requirements.yaml contains a `domain` field (e.g. `domain: my-recipe-blog.de`):

1. **Check availability:**
   check_domain("my-recipe-blog.de")
   - If NOT AVAILABLE: suggest 2–3 similar alternatives and check them too.
   - If ALREADY OWNED: skip to DNS setup.

2. **Confirm with user (MANDATORY before any purchase):**
   confirm_with_user(
     "Domain:  my-recipe-blog.de\n"
     "Price:   €X.XX / year (Cloudflare at-cost, no markup)\n"
     "Action:  Register for 1 year via Cloudflare Registrar\n\n"
     "After purchase, DNS will be configured automatically:\n"
     "  www.my-recipe-blog.de  →  <railway-url>\n\n"
     "Deine Kreditkarte bei Cloudflare wird belastet.\n"
     "Bitte stelle sicher, dass eine Zahlungsmethode in deinem\n"
     "Cloudflare-Konto hinterlegt ist (dash.cloudflare.com > Billing)."
   )
   - If DECLINED: skip domain registration, report in final summary.

3. **Register domain:**
   register_domain("my-recipe-blog.de", years=1)

4. **Configure DNS to point to Railway:**
   - Get Railway URL: run_command("railway domain", cwd=project_dir)
   - Extract the <project>.up.railway.app URL from output
   - Add Railway custom domain: run_command("railway domain add my-recipe-blog.de", cwd=project_dir)
   - Add www CNAME:  configure_dns("my-recipe-blog.de", "www", "<project>.up.railway.app")
   - Add root CNAME: configure_dns("my-recipe-blog.de", "@", "<project>.up.railway.app")

5. **Wait note:** Tell the user DNS is live immediately via Cloudflare (no propagation wait
   because Cloudflare manages DNS directly after registration).

### Step 8 — Final report (no tool calls)
- All files created
- Local test results (HTTP status codes)
- GitHub repo URL
- Railway deployment URL
- Custom domain (if registered): https://www.<domain>
- Any steps that failed and require manual action
- Environment variables still needing real values (ANTHROPIC_API_KEY if placeholder was used)
- If Cloudflare credentials were missing: instructions for one-time setup

## CODE STANDARDS
- Every route that modifies data: @login_required
- init_db() called at startup in railway.toml startCommand
- STORAGE_PATH env var controls uploads/ and db path (for Railway persistent volume)
- SQLite migrations: ALTER TABLE ... in try/except to add new columns safely
- All JSON DB fields: use json.loads/dumps with ensure_ascii=False
- IDs: uuid.uuid4().hex
- File uploads: save with uuid filename, original extension preserved
- Claude API: system prompt uses cache_control ephemeral, model = claude-sonnet-4-6
- CSS: mobile-first, breakpoints at 900px and 600px
- i18n: data-i18n attribute on all UI strings, I18N dict in base.html JS
- Login: session['logged_in'], BLOG_PASSWORD env var, default 'admin'
- Gunicorn: --workers 2 --timeout 180
- GitHub: use `gh repo create <user>/<repo> --public --source=. --remote=origin --push`
- Railway: use `railway init --name <project>`, then `railway variables set KEY=VALUE`, then `railway up --detach`
- Read local ANTHROPIC_API_KEY with `echo $ANTHROPIC_API_KEY` before setting in Railway
- Never use interactive prompts — always use --yes, --detach, --non-interactive flags where available
- If CLI tools are missing or unauthenticated, report clearly and skip gracefully
""").strip()


# ─── Initial Prompt Builder ────────────────────────────────────────────────────

def build_initial_prompt(requirements: dict, project_dir: Path) -> str:
    req_yaml = yaml.dump(requirements, allow_unicode=True, default_flow_style=False)
    return textwrap.dedent(f"""
    ## Requirements for the new website

    ```yaml
    {req_yaml}
    ```

    ## Project output directory
    {project_dir}

    Build a completely new Flask web application for this topic from scratch.
    The project must have its own design, data model, and UI — not a copy of any
    existing project.

    Follow the workflow in your system prompt:
    1. Design a data model suited to the domain
    2. Generate ALL files fresh in the output directory
    3. Install dependencies and run local tests
    4. Set up git
    5. Report what was created

    Project name: {requirements.get("project_name", "my-website")}

    Start by designing the data model and planning the file structure,
    then create each file.
    """).strip()


# ─── Agentic Loop ─────────────────────────────────────────────────────────────

def run_agent(requirements: dict, project_dir: Path) -> None:
    client = anthropic.Anthropic()

    print(f"\n{'='*60}")
    print(f"  Website Generator Agent")
    print(f"  Project: {requirements.get('project_name', 'unknown')}")
    print(f"  Output:  {project_dir}")
    print(f"{'='*60}\n")

    project_dir.mkdir(parents=True, exist_ok=True)

    messages: list[dict] = [
        {"role": "user", "content": build_initial_prompt(requirements, project_dir)}
    ]

    iteration = 0
    max_iterations = 60  # safety cap

    while iteration < max_iterations:
        iteration += 1
        print(f"\n--- Iteration {iteration} ---")

        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=8096,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )
        except anthropic.APIError as exc:
            print(f"API error: {exc}")
            # Exponential back-off for rate limits
            time.sleep(min(2 ** iteration, 60))
            continue

        # Add assistant response to conversation history
        messages.append({"role": "assistant", "content": response.content})

        # Print any text blocks from the assistant
        for block in response.content:
            if hasattr(block, "text"):
                print(f"\n[Assistant]\n{block.text[:600]}")
                if len(block.text) > 600:
                    print("  ... [truncated for display]")

        # Stop if the model is done
        if response.stop_reason == "end_turn":
            print("\n\nAgent finished (end_turn).")
            break

        # Process tool calls
        if response.stop_reason == "tool_use":
            tool_results: list[dict] = []

            for block in response.content:
                if block.type != "tool_use":
                    continue

                tool_name = block.name
                tool_input = block.input

                # Show what is being called
                safe_input = {k: (v[:120] + "...") if isinstance(v, str) and len(v) > 120 else v
                              for k, v in tool_input.items()}
                print(f"\n  Tool: {tool_name}")
                print(f"  Input: {json.dumps(safe_input, ensure_ascii=False)[:200]}")

                # Execute
                result = execute_tool(tool_name, tool_input, project_dir)

                # Show result preview
                result_preview = str(result)[:200]
                print(f"  Result: {result_preview}")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(result),
                })

            # Feed results back into conversation
            messages.append({"role": "user", "content": tool_results})
        else:
            # Unexpected stop reason
            print(f"Unexpected stop_reason: {response.stop_reason}")
            break

    else:
        print(f"\nReached max iterations ({max_iterations}). Stopping.")


# ─── Entry Point ──────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python agent.py <requirements.yaml>")
        sys.exit(1)

    req_path = Path(sys.argv[1])
    if not req_path.exists():
        print(f"Error: requirements file not found: {req_path}")
        sys.exit(1)

    with req_path.open(encoding="utf-8") as fh:
        requirements = yaml.safe_load(fh)

    if not isinstance(requirements, dict):
        print("Error: requirements.yaml must be a YAML mapping.")
        sys.exit(1)

    project_name = requirements.get("project_name", "generated-website")
    # Sanitize project name for use as directory
    safe_name = "".join(c if c.isalnum() or c in "-_" else "-" for c in project_name)
    project_dir = OUTPUT_BASE / safe_name

    run_agent(requirements, project_dir)

    print(f"\nProject generated at: {project_dir}")


if __name__ == "__main__":
    main()
