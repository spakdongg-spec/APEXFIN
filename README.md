# APEXFIN

A forkable **financial data engineering reference skeleton**: medallion layers,
a five-layer architecture, a fail-loud quality gate, and a fully offline static
HTML dashboard.

> The decision engine is a deliberately naive, demonstration-only implementation.
> It exists to exercise the pipeline end-to-end and is **not investment advice**.

## Dashboard

The dashboard is a static `dist/index.html` rendered from a single `datapack`
JSON object. It is intentionally dependency-free at view time:

- **Jinja2** template (`templates/dashboard.html`) rendered by the backend
  (`apexfin render`) to `dist/index.html`.
- **ECharts 6.1.0** is vendored at `static/vendor/echarts.min.js` — no CDN at
  runtime, so the page works fully offline (open `dist/index.html` directly).
- **Lucide** icons are shipped as an inline SVG sprite (`static/sprite.svg`,
  inlined into the page via `templates/_sprite.svg.html`) — zero network requests
  for icons, works under `file://`.
- **Design tokens** live in `static/tokens.css` (dark default + light + CVD
  palettes). Component styles are in `static/dashboard.css`.
- Chart engine missing or JS disabled → each chart degrades to a server-rendered
  data table (`<details>`), so the page is always a complete, readable report.

### Generate it

```bash
# via the CLI
apexfin render

# or via the demo target
make demo
```

### Hard rules (CI-enforced)

- **Zero emoji** anywhere in `templates/`, `static/`, `docs/`. Icons are Lucide
  `#icon-*` references only.
- **No hardcoded colors** outside `tokens.css` (except `#fff`/`#000`). Every
  color comes from a CSS custom property.
- **No purple→pink gradient**, no glow + glassmorphism, no bounce/elastic easing.
- **State is never color alone** — every status is encoded by icon shape +
  color + text (WCAG 1.4.1). Market direction (red up / green down, CN
  convention) and system status use strictly isolated color channels.

### Icons

`config/icons.yaml` is the semantic-locked whitelist of 27 Lucide icons
(`lucide-static@1.28.0`). `tools/build_sprite.py` downloads them, emits
`static/sprite.svg` + `templates/_sprite.svg.html`, and writes
`config/icons.lock` (per-icon SHA-256). It fails loudly (exit 3) if any icon 404s,
the Lucide version drifts, or the lock cannot be written.

## License

MIT
