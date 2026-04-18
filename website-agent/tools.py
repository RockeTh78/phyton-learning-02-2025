"""
Tool implementations for the website generator agent.

- create_file:       Write a file to the project output directory
- read_file:         Read from the reference travel blog
- run_command:       Execute a shell command with timeout
- test_endpoint:     HTTP GET with timeout, returns status + body excerpt
- list_files:        Recursive file listing (tree-style)
- append_to_file:    Append content to an existing file
- check_domain:      Check domain availability + price via Porkbun API
- confirm_with_user: Pause and wait for user confirmation in the terminal
- register_domain:   Register a domain via Porkbun API
- configure_dns:     Add DNS records at Porkbun (CNAME/ALIAS for Railway)
"""

import os
import subprocess
import traceback
from pathlib import Path

import requests

REFERENCE_BLOG = Path("/Users/thomashoche/DEV/phyton-learning-02-2025/travel-blog")


# ─── create_file ──────────────────────────────────────────────────────────────

def create_file(path: str, content: str, project_dir: Path) -> str:
    """Write `content` to `path` (relative to project_dir). Creates parents."""
    try:
        target = project_dir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"OK: created {path} ({len(content)} chars)"
    except Exception as exc:
        return f"ERROR creating {path}: {exc}\n{traceback.format_exc()}"


# ─── append_to_file ───────────────────────────────────────────────────────────

def append_to_file(path: str, content: str, project_dir: Path) -> str:
    """Append `content` to an existing file at `path` (relative to project_dir)."""
    try:
        target = project_dir / path
        if not target.exists():
            return f"ERROR: {path} does not exist. Use create_file first."
        with target.open("a", encoding="utf-8") as fh:
            fh.write(content)
        return f"OK: appended {len(content)} chars to {path}"
    except Exception as exc:
        return f"ERROR appending to {path}: {exc}"


# ─── read_file ────────────────────────────────────────────────────────────────

def read_file(path: str) -> str:
    """
    Read a file from the REFERENCE travel blog.

    `path` is relative to the travel-blog root, e.g. "app.py" or "templates/base.html".
    Pass an absolute path to read from anywhere else.
    """
    try:
        target = Path(path) if Path(path).is_absolute() else REFERENCE_BLOG / path
        if not target.exists():
            return f"ERROR: {target} not found"
        text = target.read_text(encoding="utf-8")
        # Cap at 50 000 chars to keep context manageable
        if len(text) > 50_000:
            text = text[:50_000] + "\n... [truncated]"
        return text
    except Exception as exc:
        return f"ERROR reading {path}: {exc}"


# ─── run_command ──────────────────────────────────────────────────────────────

def run_command(command: str, cwd: str | None = None) -> str:
    """
    Run `command` in a shell.
    `cwd` defaults to the current working directory.
    Returns combined stdout + stderr (truncated at 8 000 chars).
    Timeout: 120 s.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd or os.getcwd(),
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = result.stdout + result.stderr
        if len(output) > 8_000:
            output = output[:8_000] + "\n... [truncated]"
        exit_label = "OK" if result.returncode == 0 else f"EXIT {result.returncode}"
        return f"[{exit_label}]\n{output}".strip()
    except subprocess.TimeoutExpired:
        return "ERROR: command timed out after 120 s"
    except Exception as exc:
        return f"ERROR running command: {exc}\n{traceback.format_exc()}"


# ─── test_endpoint ────────────────────────────────────────────────────────────

def test_endpoint(url: str) -> str:
    """
    HTTP GET `url` with a 10 s timeout.
    Returns status code and first 500 chars of the response body.
    """
    try:
        resp = requests.get(url, timeout=10, allow_redirects=True)
        body = resp.text[:500]
        return f"STATUS {resp.status_code}\n{body}"
    except requests.exceptions.ConnectionError:
        return "ERROR: connection refused (server not running?)"
    except requests.exceptions.Timeout:
        return "ERROR: request timed out (10 s)"
    except Exception as exc:
        return f"ERROR: {exc}"


# ─── list_files ───────────────────────────────────────────────────────────────

def list_files(directory: str, project_dir: Path | None = None) -> str:
    """
    Recursively list files under `directory`.

    If `project_dir` is given:
      - paths starting with "/" are treated as absolute
      - otherwise relative to project_dir
    Falls back to the reference blog if the resolved path doesn't exist.
    """
    try:
        if Path(directory).is_absolute():
            base = Path(directory)
        elif project_dir and (project_dir / directory).exists():
            base = project_dir / directory
        else:
            base = REFERENCE_BLOG / directory

        if not base.exists():
            return f"ERROR: directory not found: {base}"

        lines: list[str] = []
        for p in sorted(base.rglob("*")):
            if p.is_file():
                rel = p.relative_to(base)
                lines.append(str(rel))
        return "\n".join(lines) if lines else "(empty)"
    except Exception as exc:
        return f"ERROR listing {directory}: {exc}"


# ─── Domain Registration & DNS (Cloudflare API) ───────────────────────────────
# Cloudflare advantages over other registrars:
#   - At-cost domain prices (no markup)
#   - Free DNS with global CDN/proxy
#   - Clean REST API with a single API token
#   - User-friendly dashboard at dash.cloudflare.com
#   - Perfect Railway integration (proxy mode for DDoS protection)
#
# Setup (one-time):
#   1. Create account at cloudflare.com
#   2. Add payment method in Billing > Payment Methods
#   3. Create API token: My Profile > API Tokens > Create Token
#      Use "Edit zone DNS" + "Registrar: Edit" permissions, or use Global API Key
#   4. Find Account ID: any Zone overview page (right sidebar)
#   5. Set env vars: CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID

CF_BASE = "https://api.cloudflare.com/client/v4"


def _cf_headers() -> dict[str, str]:
    """Return Authorization headers from CLOUDFLARE_API_TOKEN env var."""
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    if not token:
        raise RuntimeError(
            "CLOUDFLARE_API_TOKEN must be set. "
            "Create one at dash.cloudflare.com > My Profile > API Tokens. "
            "Grant 'Registrar: Edit' and 'Zone: DNS: Edit' permissions."
        )
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _cf_account_id() -> str:
    """Return Cloudflare Account ID from env var."""
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    if not account_id:
        raise RuntimeError(
            "CLOUDFLARE_ACCOUNT_ID must be set. "
            "Find it on any Zone overview page in the right sidebar at dash.cloudflare.com."
        )
    return account_id


def _cf_get_zone_id(domain: str, headers: dict) -> str | None:
    """Look up the Cloudflare Zone ID for a domain."""
    resp = requests.get(
        f"{CF_BASE}/zones",
        headers=headers,
        params={"name": domain, "status": "active"},
        timeout=15,
    )
    data = resp.json()
    zones = data.get("result", [])
    return zones[0]["id"] if zones else None


def check_domain(domain: str) -> str:
    """
    Check if a domain is available for registration via Cloudflare Registrar API
    and return the price.
    """
    try:
        headers = _cf_headers()
        account_id = _cf_account_id()
        domain = domain.strip().lower()

        resp = requests.get(
            f"{CF_BASE}/accounts/{account_id}/registrar/domains/{domain}",
            headers=headers,
            timeout=15,
        )
        data = resp.json()

        # If the domain is already registered in this account
        if data.get("success") and data.get("result"):
            result = data["result"]
            return (
                f"ALREADY OWNED: {domain} is already in your Cloudflare account.\n"
                f"Status: {result.get('status', 'N/A')}\n"
                f"Expires: {result.get('expires_at', 'N/A')}"
            )

        # Try the dedicated availability check endpoint
        avail_resp = requests.get(
            f"{CF_BASE}/accounts/{account_id}/registrar/availability",
            headers=headers,
            params={"domains": domain},
            timeout=15,
        )
        avail_data = avail_resp.json()

        if avail_data.get("success"):
            results = avail_data.get("result", [])
            if results:
                item = results[0]
                available = item.get("available", False)
                price = item.get("price", "?")
                currency = item.get("currency", "USD")
                if available:
                    return (
                        f"AVAILABLE: {domain}\n"
                        f"Registration price: {price} {currency}/year\n"
                        f"Provider: Cloudflare Registrar (at-cost, no markup)\n"
                        f"Includes: Free DNS, DDoS protection, WHOIS privacy"
                    )
                else:
                    return f"NOT AVAILABLE: {domain} is already taken."

        # Fallback message if the API response was unexpected
        return (
            f"AVAILABILITY UNKNOWN for {domain}.\n"
            f"API response: {avail_data}\n"
            f"You can also check manually at dash.cloudflare.com/registrar"
        )

    except RuntimeError as exc:
        return f"CONFIG ERROR: {exc}"
    except Exception as exc:
        return f"ERROR checking domain '{domain}': {exc}\n{traceback.format_exc()}"


def confirm_with_user(message: str) -> str:
    """
    Print a summary message to the terminal and wait for user confirmation.
    Blocks until the user types 'ja' or 'nein'. Returns the result.
    """
    print("\n" + "=" * 60)
    print("  BESTÄTIGUNG ERFORDERLICH")
    print("=" * 60)
    print(message)
    print("=" * 60)
    try:
        response = input("\nBitte bestätigen (ja / nein): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        response = "nein"
    print(f"  Eingabe: {response}")
    print("=" * 60 + "\n")
    if response in ("ja", "j", "yes", "y"):
        return "CONFIRMED: User typed '{}'".format(response)
    else:
        return "DECLINED: User typed '{}'. Do NOT proceed with the purchase.".format(response)


def register_domain(domain: str, years: int = 1) -> str:
    """
    Register a domain via Cloudflare Registrar API.
    Only call this after confirm_with_user returned CONFIRMED.
    The Cloudflare account must have a valid payment method on file.
    """
    try:
        headers = _cf_headers()
        account_id = _cf_account_id()
        domain = domain.strip().lower()

        resp = requests.post(
            f"{CF_BASE}/accounts/{account_id}/registrar/domains/{domain}",
            headers=headers,
            json={
                "auto_renew": False,
                "privacy": True,
                "years": years,
            },
            timeout=30,
        )
        data = resp.json()

        if data.get("success"):
            result = data.get("result", {})
            return (
                f"SUCCESS: Domain '{domain}' registered for {years} year(s).\n"
                f"Status: {result.get('status', 'N/A')}\n"
                f"Expires: {result.get('expires_at', 'N/A')}\n"
                f"WHOIS privacy: enabled\n"
                f"DNS is now managed via Cloudflare. Nameservers assigned automatically."
            )
        else:
            errors = data.get("errors", [])
            msg = "; ".join(e.get("message", str(e)) for e in errors) if errors else str(data)
            return f"ERROR registering '{domain}': {msg}"

    except RuntimeError as exc:
        return f"CONFIG ERROR: {exc}"
    except Exception as exc:
        return f"ERROR registering domain '{domain}': {exc}\n{traceback.format_exc()}"


def configure_dns(domain: str, host: str, answer: str, record_type: str = "CNAME") -> str:
    """
    Add a DNS record to a Cloudflare-managed domain.
    Used to point the custom domain (or www subdomain) to the Railway deployment.

    Cloudflare proxy (orange cloud) is enabled for CNAME records so Railway gets
    free DDoS protection and CDN. Disable proxied=True if Railway requires direct
    TLS termination (e.g. for WebSockets or custom TLS certs).

    Args:
        domain:      Root domain, e.g. 'my-blog.de'
        host:        Name, e.g. 'www', '@' for root, or 'my-blog.de'
        answer:      Target, e.g. 'myapp.up.railway.app'
        record_type: 'CNAME' (most common) or 'A'
    """
    try:
        headers = _cf_headers()
        domain = domain.strip().lower()
        host = host.strip()
        # Cloudflare uses '@' for root
        cf_name = host if host and host != "" else "@"

        # Get Zone ID for the domain
        zone_id = _cf_get_zone_id(domain, headers)
        if not zone_id:
            return (
                f"ERROR: No active Cloudflare zone found for '{domain}'.\n"
                "The domain must be registered/transferred to Cloudflare first, "
                "and the zone must be active (nameservers propagated)."
            )

        # For CNAME records, enable Cloudflare proxy for CDN + DDoS protection.
        # Proxied mode also hides the Railway origin IP.
        proxied = record_type.upper() == "CNAME"

        resp = requests.post(
            f"{CF_BASE}/zones/{zone_id}/dns_records",
            headers=headers,
            json={
                "type": record_type.upper(),
                "name": cf_name,
                "content": answer.rstrip("."),
                "ttl": 1,        # 1 = Auto (Cloudflare manages TTL when proxied)
                "proxied": proxied,
            },
            timeout=15,
        )
        data = resp.json()

        if data.get("success"):
            result = data.get("result", {})
            proxy_note = " (Cloudflare proxy enabled: free CDN + DDoS protection)" if proxied else ""
            return (
                f"SUCCESS: DNS {record_type} record created{proxy_note}.\n"
                f"  {cf_name}.{domain}  →  {answer}\n"
                f"  Record ID: {result.get('id', 'N/A')}\n"
                f"  Proxied: {proxied}\n"
                f"DNS is live immediately via Cloudflare (no propagation wait)."
            )
        else:
            errors = data.get("errors", [])
            msg = "; ".join(e.get("message", str(e)) for e in errors) if errors else str(data)
            return f"ERROR creating DNS record for '{domain}': {msg}"

    except RuntimeError as exc:
        return f"CONFIG ERROR: {exc}"
    except Exception as exc:
        return f"ERROR configuring DNS for '{domain}': {exc}\n{traceback.format_exc()}"


# ─── Dispatch ─────────────────────────────────────────────────────────────────

def execute_tool(name: str, inputs: dict, project_dir: Path) -> str:
    """Dispatch a tool call by name."""
    try:
        if name == "create_file":
            return create_file(inputs["path"], inputs["content"], project_dir)
        elif name == "append_to_file":
            return append_to_file(inputs["path"], inputs["content"], project_dir)
        elif name == "read_file":
            return read_file(inputs["path"])
        elif name == "run_command":
            return run_command(inputs["command"], inputs.get("cwd"))
        elif name == "test_endpoint":
            return test_endpoint(inputs["url"])
        elif name == "list_files":
            return list_files(inputs["directory"], project_dir)
        elif name == "check_domain":
            return check_domain(inputs["domain"])
        elif name == "confirm_with_user":
            return confirm_with_user(inputs["message"])
        elif name == "register_domain":
            return register_domain(inputs["domain"], inputs.get("years", 1))
        elif name == "configure_dns":
            return configure_dns(
                inputs["domain"],
                inputs["host"],
                inputs["answer"],
                inputs.get("record_type", "CNAME"),
            )
        else:
            return f"ERROR: unknown tool '{name}'"
    except KeyError as exc:
        return f"ERROR: missing required parameter {exc} for tool '{name}'"
    except Exception as exc:
        return f"ERROR in tool '{name}': {exc}\n{traceback.format_exc()}"
