SGGE2.0 — Cloudflare Pages direct-upload static website (field-test package)

This folder is itself the finished website. Upload these contents (or the ZIP
containing them at its root) to a NEW Cloudflare Pages project using Direct Upload.
Do not select the existing Purple Python Browser project.

Visitors: open the site's pages.dev URL to play. No login, game server, Python
installation, or separate game download. WebAssembly runtime loads from
https://pygame-web.github.io/cdn/0.9.3/ (standard Pygbag CDN); an internet
connection is required to fetch it on initial use.

LOCAL BROWSER TEST (Windows):
  1. Open PowerShell in the folder containing index.html.
  2. Run: python -m http.server 8000
  3. Visit: http://localhost:8000
  4. You are serving static files only. The server does not run game logic.

SAVES AND SETTINGS: same browser origin/profile only, using localStorage.
F5 quick-save, F9 quick-load, F6 save panel, F7 export backup, F8 import.
Export backups before clearing browser site data or moving to a new URL.
The E1.0 save namespace and JSON schema are retained for compatibility.
No analytics, player accounts, or game state sent to the Cloudflare host.

This build recreates Pygbag's published static template layout and bundle
format. The source and asset file passed Python syntax and JSON checks;
the actual CDN/WebAssembly launch must still be field tested in Opera GX.
