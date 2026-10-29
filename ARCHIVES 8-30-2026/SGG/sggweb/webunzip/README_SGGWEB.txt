Spiffy's Gift — versioned Cloudflare Pages website

This ZIP is the direct-upload site root. Upload THIS ZIP to a new Cloudflare Pages project
using Workers & Pages > Create > Upload your static files. Do not upload the old SGGE2.0
ZIP as the site root. No GitHub integration is required.

/index.html             Browser edition listing (currently SGGE 2.0)
/SGGE2.0/index.html     SGGE 2.0 game page
/SGGE2.0/sgge2.tar.gz  Game assets
/SGGE2.0/sgge2.apk     Pygbag ZIP alternative
/SGGE2.0/favicon.png    Game favicon
/_headers               Cloudflare Pages file response headers

To add editions later, add a new subdirectory and an entry to root index.html.
Do not overwrite archived edition files unless you explicitly intend to revise them.

This package is static but requires internet access to fetch Pygbag runtime assets
from https://pygame-web.github.io/cdn/0.9.3/ at runtime.
The game has NOT been field-tested in the browser by this repackaging process.

Saves are stored in the player's browser storage; save data may be shared by editions
if their storage keys coincide. Export important backups before changing editions.

The original SGGE 2.0 release's README is preserved under SGGE2.0/.
