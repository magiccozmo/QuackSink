#!/usr/bin/env python3
"""
America.gov passive runtime forensic capture.

Purpose:
  Capture a fresh, public, read-only browser session of America.gov and record:
    - raw HTTP response bodies for runtime resources
    - request/response metadata
    - Playwright HAR with embedded content
    - Chromium DevTools script sources, including inline/evaluated scripts when exposed
    - DOM snapshots before/after typing "hotdog"
    - DOM mutation log
    - console/page-error/network-failure log
    - localStorage/sessionStorage and Playwright storage_state
    - screenshots and a Playwright trace
    - event-listener metadata on document/window/form/textarea after the trigger
    - resource/performance manifest and worker URLs

Safety:
  - Opens a fresh temporary browser profile.
  - Does NOT log into America.gov.
  - Does NOT click Login or submit the chat.
  - Uses only the public homepage and types the harmless test string "hotdog".
  - HAR and metadata are scrubbed of Cookie/Set-Cookie/Authorization before the
    final public-safe copy is produced. The raw Playwright HAR is retained locally
    in the private capture directory; do not publish it without review.

Requires:
  pip install playwright
  python -m playwright install chromium

Example:
  python america_gov_runtime_capture.py
  python america_gov_runtime_capture.py --url https://america.gov --linger 10
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, unquote

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


SENSITIVE_HEADER_NAMES = {
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
}

SKIP_CONTENT_PREFIXES = (
    "video/",
    "audio/",
)

DEFAULT_MAX_BODY_MB = 50


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def safe_json_dump(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8", errors="replace")).hexdigest()


def sanitize_basename(url: str, content_type: str) -> str:
    parsed = urlparse(url)
    base = unquote(Path(parsed.path).name) or "resource"
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base)
    base = base[:120]

    if "." not in base:
        ct = content_type.lower()
        ext = ".bin"
        if "javascript" in ct or "ecmascript" in ct:
            ext = ".js"
        elif "css" in ct:
            ext = ".css"
        elif "html" in ct:
            ext = ".html"
        elif "json" in ct:
            ext = ".json"
        elif "svg" in ct:
            ext = ".svg"
        elif "webp" in ct:
            ext = ".webp"
        elif "png" in ct:
            ext = ".png"
        elif "woff2" in ct:
            ext = ".woff2"
        elif "woff" in ct:
            ext = ".woff"
        elif "wasm" in ct:
            ext = ".wasm"
        base += ext

    return base


def scrub_headers(headers: dict[str, str] | None) -> dict[str, str]:
    if not headers:
        return {}
    out: dict[str, str] = {}
    for k, v in headers.items():
        if k.lower() in SENSITIVE_HEADER_NAMES:
            out[k] = "[REDACTED]"
        else:
            out[k] = v
    return out


def scrub_har(har_path: Path) -> None:
    """Create a public-safe HAR beside the raw HAR."""
    public_path = har_path.with_name("network_trace_PUBLIC_SAFE.har")
    data = json.loads(har_path.read_text(encoding="utf-8"))

    def scrub_header_list(items: list[dict[str, Any]]) -> None:
        for item in items:
            name = str(item.get("name", ""))
            if name.lower() in SENSITIVE_HEADER_NAMES:
                item["value"] = "[REDACTED]"

    for entry in data.get("log", {}).get("entries", []):
        req = entry.get("request", {})
        resp = entry.get("response", {})
        scrub_header_list(req.get("headers", []))
        scrub_header_list(resp.get("headers", []))
        # HAR cookies can contain session identifiers even if Cookie headers are scrubbed.
        req["cookies"] = []
        resp["cookies"] = []

    safe_json_dump(public_path, data)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Passive America.gov runtime capture")
    parser.add_argument("--url", default="https://america.gov", help="Target public URL")
    parser.add_argument("--out", default=None, help="Output directory")
    parser.add_argument("--linger", type=float, default=8.0, help="Seconds to leave page running after hotdog")
    parser.add_argument("--settle", type=float, default=8.0, help="Seconds to allow runtime after initial navigation")
    parser.add_argument("--max-body-mb", type=float, default=DEFAULT_MAX_BODY_MB, help="Maximum individual response body to save")
    parser.add_argument("--executable", default=None, help="Optional Chromium/Chrome/Opera executable path")
    args = parser.parse_args()

    stamp = utc_stamp()
    out_dir = Path(args.out or f"AmericaGov_RUNTIME_{stamp}").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    responses_dir = out_dir / "responses"
    scripts_dir = out_dir / "debugger_scripts"
    screenshots_dir = out_dir / "screenshots"
    logs_dir = out_dir / "logs"
    responses_dir.mkdir(exist_ok=True)
    scripts_dir.mkdir(exist_ok=True)
    screenshots_dir.mkdir(exist_ok=True)
    logs_dir.mkdir(exist_ok=True)

    raw_har_path = out_dir / "network_trace_RAW.har"
    trace_path = out_dir / "playwright_trace.zip"

    manifest: list[dict[str, Any]] = []
    network_failures: list[dict[str, Any]] = []
    console_events: list[dict[str, Any]] = []
    page_errors: list[dict[str, Any]] = []
    worker_events: list[dict[str, Any]] = []
    mutation_events: list[dict[str, Any]] = []
    listener_snapshots: dict[str, Any] = {}
    debugger_scripts: dict[str, dict[str, Any]] = {}

    max_body_bytes = int(args.max_body_mb * 1024 * 1024)

    def log_jsonl(path: Path, obj: Any) -> None:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")

    with sync_playwright() as p:
        launch_kwargs: dict[str, Any] = {
            "headless": False,
            "viewport": {"width": 1440, "height": 1000},
            "record_har_path": str(raw_har_path),
            "record_har_content": "embed",
            "record_har_mode": "full",
            "accept_downloads": False,
        }
        if args.executable:
            launch_kwargs["executable_path"] = args.executable

        # Fresh, isolated public-session profile.
        profile_dir = out_dir / "browser_profile_TEMP_DO_NOT_PUBLISH"
        context = p.chromium.launch_persistent_context(str(profile_dir), **launch_kwargs)
        context.set_default_timeout(20_000)

        # Playwright trace is an additional, useful record of the rendered page/action timeline.
        context.tracing.start(screenshots=True, snapshots=True, sources=True)

        cdp_sessions: dict[int, Any] = {}
        bound_pages: set[int] = set()

        def install_cdp_for_page(page) -> None:
            try:
                session = context.new_cdp_session(page)
                cdp_sessions[id(page)] = session
                session.send("Debugger.enable")

                def on_script_parsed(params: dict[str, Any]) -> None:
                    sid = params.get("scriptId")
                    if sid is None:
                        return
                    debugger_scripts.setdefault(str(sid), {
                        "scriptId": str(sid),
                        "url": params.get("url", ""),
                        "startLine": params.get("startLine"),
                        "startColumn": params.get("startColumn"),
                        "endLine": params.get("endLine"),
                        "endColumn": params.get("endColumn"),
                        "executionContextId": params.get("executionContextId"),
                        "hash": params.get("hash"),
                        "isLiveEdit": params.get("isLiveEdit"),
                        "sourceMapURL": params.get("sourceMapURL", ""),
                        "embedderName": params.get("embedderName", ""),
                    })

                session.on("Debugger.scriptParsed", on_script_parsed)
            except Exception as exc:
                log_jsonl(logs_dir / "errors.jsonl", {"kind": "cdp_setup", "error": repr(exc)})

        for existing_page in context.pages:
            install_cdp_for_page(existing_page)

        def on_response(response) -> None:
            try:
                url = response.url
                ct = (response.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
                request = response.request
                entry_key = f"{request.method} {url}"

                record: dict[str, Any] = {
                    "timestamp_utc": utc_stamp(),
                    "url": url,
                    "method": request.method,
                    "status": response.status,
                    "status_text": response.status_text,
                    "resource_type": request.resource_type,
                    "content_type": ct,
                    "request_headers": scrub_headers(dict(request.headers)),
                    "response_headers": scrub_headers(dict(response.headers)),
                    "from_service_worker": bool(response.from_service_worker),
                }

                # Save each response body. The filename is content-hash based, so repeated
                # requests with identical bodies naturally deduplicate on disk while the manifest
                # preserves every network event.
                should_save = not any(ct.startswith(prefix) for prefix in SKIP_CONTENT_PREFIXES)
                if should_save:
                    try:
                        body = response.body()
                        record["body_size"] = len(body)
                        record["body_sha256"] = sha256_bytes(body)
                        if len(body) <= max_body_bytes:
                            digest = sha256_bytes(body)[:16]
                            basename = sanitize_basename(url, ct)
                            dest = responses_dir / f"{digest}__{basename}"
                            if not dest.exists():
                                dest.write_bytes(body)
                            record["body_file"] = str(dest.relative_to(out_dir))
                        else:
                            record["body_file"] = None
                            record["body_skipped"] = f"larger than {args.max_body_mb} MB"
                    except Exception as exc:
                        record["body_error"] = repr(exc)

                manifest.append(record)
                log_jsonl(logs_dir / "responses.jsonl", record)
            except Exception as exc:
                log_jsonl(logs_dir / "errors.jsonl", {"kind": "response_handler", "error": repr(exc)})

        context.on("response", on_response)

        def on_request_failed(request) -> None:
            item = {
                "timestamp_utc": utc_stamp(),
                "url": request.url,
                "method": request.method,
                "resource_type": request.resource_type,
                "failure": request.failure,
                "headers": scrub_headers(dict(request.headers)),
            }
            network_failures.append(item)
            log_jsonl(logs_dir / "network_failures.jsonl", item)

        context.on("requestfailed", on_request_failed)

        def bind_page(page) -> None:
            page_key = id(page)
            if page_key in bound_pages:
                return
            bound_pages.add(page_key)
            install_cdp_for_page(page)

            page.on("console", lambda msg: (
                console_events.append({
                    "timestamp_utc": utc_stamp(),
                    "type": msg.type,
                    "text": msg.text,
                    "location": msg.location,
                })
            ))
            page.on("pageerror", lambda exc: (
                page_errors.append({"timestamp_utc": utc_stamp(), "error": str(exc)})
            ))
            page.on("worker", lambda worker: (
                worker_events.append({"timestamp_utc": utc_stamp(), "event": "created", "url": worker.url})
            ))

            # Installed before navigation where possible. This is observational: it only records
            # DOM mutations and selected input activity, it does not prevent or alter them.
            try:
                page.add_init_script("""
                    (() => {
                      window.__QS_FORENSICS__ = { mutations: [], inputs: [] };
                      const pathOf = (node) => {
                        try {
                          if (!node || node.nodeType !== 1) return node?.nodeName || 'unknown';
                          const parts = [];
                          let cur = node;
                          for (let i = 0; i < 6 && cur && cur.nodeType === 1; i++, cur = cur.parentElement) {
                            let s = cur.tagName.toLowerCase();
                            if (cur.id) s += '#' + cur.id;
                            if (cur.classList && cur.classList.length) s += '.' + Array.from(cur.classList).slice(0, 3).join('.');
                            parts.push(s);
                          }
                          return parts.join(' > ');
                        } catch (_) { return 'unknown'; }
                      };
                      const obs = new MutationObserver((records) => {
                        for (const r of records) {
                          window.__QS_FORENSICS__.mutations.push({
                            t: performance.now(),
                            type: r.type,
                            target: pathOf(r.target),
                            attributeName: r.attributeName || null,
                            added: r.addedNodes ? r.addedNodes.length : 0,
                            removed: r.removedNodes ? r.removedNodes.length : 0,
                            text: r.type === 'characterData' ? String(r.target?.data || '').slice(0, 300) : null
                          });
                        }
                      });
                      const start = () => {
                        if (document.documentElement) obs.observe(document.documentElement, {
                          subtree: true,
                          childList: true,
                          attributes: true,
                          characterData: true
                        });
                      };
                      if (document.documentElement) start();
                      else document.addEventListener('DOMContentLoaded', start, {once: true});

                      document.addEventListener('input', (e) => {
                        try {
                          const el = e.target;
                          window.__QS_FORENSICS__.inputs.push({
                            t: performance.now(),
                            type: 'input',
                            target: pathOf(el),
                            name: el?.getAttribute?.('name') || null,
                            value: typeof el?.value === 'string' ? el.value : null
                          });
                        } catch (_) {}
                      }, true);
                    })();
                """)
            except Exception as exc:
                log_jsonl(logs_dir / "errors.jsonl", {"kind": "init_script", "error": repr(exc)})

        # Bind pages after defining handlers. Popups/new tabs are bound too.
        context.on("page", bind_page)
        page = context.pages[0] if context.pages else context.new_page()
        bind_page(page)

        start_meta = {
            "capture_started_utc": utc_stamp(),
            "target_url": args.url,
            "browser": "Chromium via Playwright",
            "headless": False,
            "max_body_mb": args.max_body_mb,
            "hotdog_trigger": "type hotdog into the public Ask America input; do not submit",
        }
        safe_json_dump(out_dir / "capture_metadata.json", start_meta)

        print(f"[1/6] Opening {args.url}")
        page.goto(args.url, wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_timeout(int(args.settle * 1000))

        write_text(out_dir / "before_hotdog.html", page.content())
        page.screenshot(path=str(screenshots_dir / "before_hotdog.png"), full_page=True)
        safe_json_dump(out_dir / "before_hotdog_storage.json", {
            "localStorage": page.evaluate("() => Object.fromEntries(Object.entries(localStorage))"),
            "sessionStorage": page.evaluate("() => Object.fromEntries(Object.entries(sessionStorage))"),
        })

        print("[2/6] Capturing resource/performance state before trigger")
        safe_json_dump(out_dir / "before_hotdog_performance.json", page.evaluate("""
            () => performance.getEntriesByType('resource').map(r => ({
              name: r.name,
              initiatorType: r.initiatorType,
              startTime: r.startTime,
              duration: r.duration,
              transferSize: r.transferSize,
              encodedBodySize: r.encodedBodySize,
              decodedBodySize: r.decodedBodySize
            }))
        """))

        # Try to locate the public chat input.
        candidates = [
            'textarea[name="message"]',
            'textarea[placeholder="Ask anything…"]',
            'textarea[placeholder*="Ask anything"]',
            'textarea',
        ]
        box = None
        for selector in candidates:
            try:
                loc = page.locator(selector).first
                if loc.is_visible(timeout=1500):
                    box = loc
                    break
            except Exception:
                continue

        if box is None:
            write_text(out_dir / "TRIGGER_NOT_FOUND.txt", "Could not find the public chat textarea. No interaction performed.\n")
            print("[3/6] Could not find the public input; capture completed without trigger.")
        else:
            print("[3/6] Typing 'hotdog' one character at a time; NOT submitting")
            box.click()
            box.press_sequentially("hotdog", delay=180)
            page.wait_for_timeout(3000)
            write_text(out_dir / "after_hotdog.html", page.content())
            page.screenshot(path=str(screenshots_dir / "after_hotdog.png"), full_page=True)

            # Pull observational init-script data.
            try:
                forensic_state = page.evaluate("""() => ({
                  mutations: window.__QS_FORENSICS__?.mutations || [],
                  inputs: window.__QS_FORENSICS__?.inputs || []
                })""")
                mutation_events.extend(forensic_state.get("mutations", []))
                safe_json_dump(out_dir / "dom_mutations_and_inputs.json", forensic_state)
            except Exception as exc:
                log_jsonl(logs_dir / "errors.jsonl", {"kind": "forensics_read", "error": repr(exc)})

            safe_json_dump(out_dir / "after_hotdog_storage.json", {
                "localStorage": page.evaluate("() => Object.fromEntries(Object.entries(localStorage))"),
                "sessionStorage": page.evaluate("() => Object.fromEntries(Object.entries(sessionStorage))"),
            })

            print(f"[4/6] Leaving page alive for {args.linger:g}s to catch delayed runtime work")
            page.wait_for_timeout(int(args.linger * 1000))

            safe_json_dump(out_dir / "after_hotdog_performance.json", page.evaluate("""
                () => performance.getEntriesByType('resource').map(r => ({
                  name: r.name,
                  initiatorType: r.initiatorType,
                  startTime: r.startTime,
                  duration: r.duration,
                  transferSize: r.transferSize,
                  encodedBodySize: r.encodedBodySize,
                  decodedBodySize: r.decodedBodySize
                }))
            """))

        print("[5/6] Capturing DOM event-listener metadata and debugger script sources")

        # Collect script source text from scripts known to Chromium's Debugger domain.
        for session in list(cdp_sessions.values()):
            for sid, meta in list(debugger_scripts.items()):
                if meta.get("source_captured"):
                    continue
                try:
                    result = session.send("Debugger.getScriptSource", {"scriptId": sid})
                    source = result.get("scriptSource", "")
                    digest = sha256_text(source)
                    fname = f"{sid}__{digest[:16]}.js.txt"
                    write_text(scripts_dir / fname, source)
                    meta["source_captured"] = True
                    meta["source_sha256"] = digest
                    meta["source_file"] = str((scripts_dir / fname).relative_to(out_dir))
                    meta["source_size"] = len(source.encode("utf-8", errors="replace"))
                except Exception as exc:
                    meta["source_error"] = repr(exc)

        # Ask Chromium for event listeners on the most relevant targets.
        session = next(iter(cdp_sessions.values()), None)
        if session is not None and page.url.startswith("http"):
            targets: dict[str, str] = {
                "window": "window",
                "document": "document",
                "body": "document.body",
                "html": "document.documentElement",
                "form": "document.querySelector('form[aria-label=\"Ask America\"]')",
                "textarea": "document.querySelector('textarea[name=\"message\"]') || document.querySelector('textarea')",
            }
            for name, expr in targets.items():
                try:
                    eval_result = session.send("Runtime.evaluate", {
                        "expression": expr,
                        "returnByValue": False,
                        "objectGroup": "qs_forensics",
                    })
                    obj = eval_result.get("result", {})
                    object_id = obj.get("objectId")
                    if not object_id:
                        listener_snapshots[name] = {"error": "no objectId", "description": obj.get("description")}
                        continue
                    listeners = session.send("DOMDebugger.getEventListeners", {
                        "objectId": object_id,
                        "depth": 1,
                        "pierce": True,
                    })
                    listener_snapshots[name] = listeners
                except Exception as exc:
                    listener_snapshots[name] = {"error": repr(exc)}

        # Final state snapshots.
        safe_json_dump(out_dir / "response_manifest.json", manifest)
        safe_json_dump(out_dir / "console_events.json", console_events)
        safe_json_dump(out_dir / "page_errors.json", page_errors)
        safe_json_dump(out_dir / "network_failures.json", network_failures)
        safe_json_dump(out_dir / "worker_events.json", worker_events)
        safe_json_dump(out_dir / "debugger_scripts_manifest.json", debugger_scripts)
        safe_json_dump(out_dir / "event_listener_metadata.json", listener_snapshots)
        final_state = context.storage_state(indexed_db=True)
        safe_json_dump(out_dir / "final_storage_state_RAW_DO_NOT_PUBLISH.json", final_state)
        public_state = dict(final_state)
        public_state["cookies"] = []
        safe_json_dump(out_dir / "final_storage_state_PUBLIC_SAFE.json", public_state)

        # Archive a compact DOM text/search report for quick repo inspection.
        try:
            report = page.evaluate("""() => ({
              url: location.href,
              title: document.title,
              html_has_hotdog: document.documentElement.outerHTML.toLowerCase().includes('hotdog'),
              textarea_value: document.querySelector('textarea[name="message"]')?.value || document.querySelector('textarea')?.value || null,
              scripts: Array.from(document.scripts).map(s => ({src: s.src || null, type: s.type || null, inlineLength: s.src ? 0 : (s.textContent || '').length})),
              stylesheets: Array.from(document.styleSheets).map(s => s.href).filter(Boolean),
              links: Array.from(document.querySelectorAll('link[href]')).map(l => ({rel: l.rel, href: l.href})),
            }))""")
            safe_json_dump(out_dir / "final_runtime_report.json", report)
        except Exception as exc:
            log_jsonl(logs_dir / "errors.jsonl", {"kind": "final_report", "error": repr(exc)})

        context.tracing.stop(path=str(trace_path))
        context.close()

    # The persistent temporary browser profile is useful for debugging locally but may contain
    # caches and browser metadata. Mark it clearly rather than silently publishing it.
    scrub_har(raw_har_path)
    write_text(out_dir / "PUBLICATION_WARNING.txt", (
        "This capture contains a raw browser HAR and a temporary browser profile.\n"
        "Do NOT publish those blindly. Use network_trace_PUBLIC_SAFE.har for the redacted HAR,\n"
        "review storage_state/cookies and response bodies, and remove browser_profile_TEMP_DO_NOT_PUBLISH\n"
        "before committing anything public. This script intentionally did not log into America.gov.\n"
    ))

    # Remove temporary profile only when explicitly requested via environment variable.
    if os.environ.get("QS_DELETE_TEMP_PROFILE", "1") == "1":
        shutil.rmtree(out_dir / "browser_profile_TEMP_DO_NOT_PUBLISH", ignore_errors=True)

    safe_json_dump(out_dir / "capture_metadata.json", {
        **json.loads((out_dir / "capture_metadata.json").read_text(encoding="utf-8")),
        "capture_finished_utc": utc_stamp(),
        "response_count": len(manifest),
        "debugger_script_count": len(debugger_scripts),
        "network_failure_count": len(network_failures),
        "page_error_count": len(page_errors),
        "worker_event_count": len(worker_events),
        "output_dir": str(out_dir),
    })

    print("[6/6] COMPLETE")
    print(f"Capture directory: {out_dir}")
    print(f"Raw HAR:          {raw_har_path}")
    print(f"Safe HAR:         {out_dir / 'network_trace_PUBLIC_SAFE.har'}")
    print(f"Responses:        {responses_dir}")
    print(f"Debugger scripts: {scripts_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted by user.", file=sys.stderr)
        raise SystemExit(130)
