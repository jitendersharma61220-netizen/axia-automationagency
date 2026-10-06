# AXIA proposal engine

Turns a website visitor into a tailored plan. The visitor picks a service on `plan.html` (WhatsApp Automation or one of the five department engines), describes their business and problem, and gives a few rough numbers. The engine then:

1. **Explains the concept** around their own problem: what the service does and why their business needs it.
2. **Builds a demo** set in their business: a WhatsApp-style conversation where their exact problem gets solved, played live on the page.
3. **Prepares a pitch deck**: eight printable slides (problem, why, solution, demo, savings, rollout, next step) that save as PDF.
4. **Sends a WhatsApp message**: their problem, the solution, the time and money saved and the extra profit, with a link back to the plan.

Savings and profit are calculated in code (`roi.py`) from the visitor's numbers and conservative per-service assumptions, which are shown next to every estimate. The tailored writing comes from the Claude API (`generator.py`); without an API key a template writer takes over so everything still runs. Generated text is cleaned of the word "AI" (brand rule).

## Run locally

```bash
cd engine
pip install -r requirements.txt
python -m axia_engine.server          # http://localhost:8080/plan.html
python -m unittest discover -s tests  # tests
```

The server also serves the `website/` folder, so the whole site works on one port.

## Configuration (environment variables)

| Variable | What it does |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key. Without it, the template writer is used. |
| `AXIA_MODEL`, `AXIA_EFFORT` | Model and effort (default `claude-opus-5-5`, `medium`). |
| `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID` | WhatsApp Cloud API credentials for the AXIA business number. Without them nothing is sent; the visitor gets a "Save to my WhatsApp" button and a chat link instead. |
| `WHATSAPP_TEMPLATE`, `WHATSAPP_TEMPLATE_LANG` | Approved template for the first message (WhatsApp requires one when the business messages first). Body parameters: `{{1}}` name, `{{2}}` service, `{{3}}` plan link. Without it, free text is sent, which only arrives within 24 hours of the visitor messaging you. |
| `AXIA_OWNER_WHATSAPP` | Number that gets a new-lead alert (default `918930522312`). |
| `PUBLIC_SITE_URL` | Where the website lives, for the plan link, e.g. `https://jitendersharma61220-netizen.github.io/axia-automationagency`. Defaults to the engine's own address. |
| `PUBLIC_API_URL` | The engine's public address, for deck links. Defaults to the request host. |
| `ALLOWED_ORIGINS` | Comma separated origins allowed to call the API (default `*`). |
| `AXIA_RATE_LIMIT` | Plans per visitor IP per hour (default 5). |
| `TRUST_PROXY` | Set to `1` behind a host's proxy so visitor IPs and https are detected. |
| `AXIA_DATA_DIR` | Where plans (`proposals/*.json`) and the lead log (`leads.jsonl`) are stored (default `engine/data`). |
| `PORT` | Port to listen on (default 8080). |

## Going live

1. Host this folder on any Python host (Render, Railway, a small VPS). Start command: `python -m axia_engine.server`. Give it a persistent disk for `AXIA_DATA_DIR`, or plans disappear on restart.
2. Set `ANTHROPIC_API_KEY`, `PUBLIC_SITE_URL`, `PUBLIC_API_URL`, `ALLOWED_ORIGINS` (the GitHub Pages origin) and `TRUST_PROXY=1`.
3. For WhatsApp sending: create a Meta WhatsApp Business app, add the AXIA number, get a permanent token and phone number ID, and get a template approved. Set the `WHATSAPP_*` variables.
4. Put the engine's address in `ENGINE_URL` in `website/build.py`, rebuild the site and publish it.

Until step 4, `plan.html` on the live site sends the visitor's details to AXIA on WhatsApp instead.

## API

- `GET /api/services`: services the visitor can pick
- `POST /api/proposals`: run the engine (JSON body with the form fields)
- `GET /api/proposals/<id>`: a saved plan, without the visitor's phone number
- `GET /p/<id>/deck`: the pitch deck as HTML slides
