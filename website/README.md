# AXIA website

Static marketing site for AXIA Automation Agency. Plain HTML, CSS and JavaScript, with Three.js for the 3D scenes (vendored in `vendor/`, so there is no build step and no CDN dependency).

## Run locally

```bash
cd website
python3 -m http.server 8000
# open http://localhost:8000
```

## Deploy

Upload the `website/` folder to any static host (Netlify, Vercel, GitHub Pages, Cloudflare Pages, Hostinger).

## Before going live

- The contact form only shows a thank-you message. Connect it to a form service (Formspree, Google Forms, a WhatsApp link) or a backend.
- Portfolio entries are sample engagements with illustrative figures. Replace them with real client results as they come in.
- Brand rule: the public site must not use the word "AI". Check new copy with:
  `grep -rniwE "ai|artificial" website --exclude-dir=vendor`
