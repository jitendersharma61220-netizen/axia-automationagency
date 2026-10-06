# AXIA website

Multi-page static site for AXIA Automation Agency. Plain HTML, CSS and JavaScript, with Three.js (vendored in `vendor/`) for the 3D workflow engine scenes.

## Pages

`index.html` (Home), `services.html`, one page per department engine (`sales.html`, `marketing.html`, `accounts.html`, `clinic.html`, `hiring.html`), `portfolio.html`, `about.html`, `contact.html`.

## Editing

Pages are generated from `build.py`, which holds all the copy and the shared layout (header, footer, call and WhatsApp buttons). Edit it, then run:

```bash
cd website
python3 build.py
```

and commit the regenerated `.html` files. `build.py` refuses to write a page that contains the word "AI" (brand rule).

- `engine.js`: the 3D automation engine. Each `<canvas data-engine>` draws inputs, processing stages, a human approval stage and outputs, configured by its `data-flow` JSON.
- `main.js`: menu, animations, portfolio filter and the contact form, which opens WhatsApp to `WHATSAPP_NUMBER` with the enquiry pre-filled.

## Run locally

```bash
cd website
python3 -m http.server 8000
# open http://localhost:8000
```

## Live site

Served by GitHub Pages from the `gh-pages` branch. After merging changes to `main`, copy the contents of `website/` (without `build.py` and `README.md`) to the root of `gh-pages` and push.
