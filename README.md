# CORPMAP — Corporate structure & beneficial-ownership mapper

> Part of the **[Cognis Neural Suite](https://github.com/cognis-digital)** by [Cognis Digital](https://cognis.digital)
> Cognis Open Collaboration License (COCL) v1.0 · domain: `osint`

[![PyPI](https://img.shields.io/pypi/v/cognis-corpmap.svg)](https://pypi.org/project/cognis-corpmap/)
[![CI](https://github.com/cognis-digital/corpmap/actions/workflows/ci.yml/badge.svg)](https://github.com/cognis-digital/corpmap/actions)
[![License: COCL 1.0](https://img.shields.io/badge/License-COCL%201.0-2b6cb0.svg)](LICENSE)

Corporate structure & beneficial-ownership mapper.

## Install

```bash
pip install cognis-corpmap
```

For local development from this repo:

```bash
pip install -e .
```

## Quick start

```bash
corpmap --version
corpmap scan demos/                          # run against bundled demo
corpmap scan demos/ --format sarif --out r.sarif --fail-on high
corpmap mcp                                   # start as MCP server (Cognis.Studio / Claude Desktop / Cursor)
```

## Built-in demo scenarios

Every scenario folder includes a `SCENARIO.md` describing what it represents and what findings to expect.

- `demos/01-vendor-onboarding-failure/` — see [`SCENARIO.md`](demos/01-vendor-onboarding-failure/SCENARIO.md)
- `demos/02-pep-board-member/` — see [`SCENARIO.md`](demos/02-pep-board-member/SCENARIO.md)
- `demos/03-clean-vendor/` — see [`SCENARIO.md`](demos/03-clean-vendor/SCENARIO.md)

## How it fits the Cognis Neural Suite

This tool is one of 52 in the [Cognis Neural Suite](https://github.com/cognis-digital). The full suite + launcher lives at:

- Suite landing: https://cognis.digital
- All 52 repos: https://github.com/cognis-digital
- Cognis.Studio (Enterprise AI Workforce, MCP host): https://cognis.studio

Every Suite tool ships an MCP server, so Cognis.Studio agents can call them as scoped capabilities.

## License

Source-available under the **Cognis Open Collaboration License (COCL) v1.0** — free for personal, internal-evaluation, research, and educational use; **commercial / production use requires a license** (licensing@cognis.digital). See [LICENSE](LICENSE) and [CONTRIBUTING.md](CONTRIBUTING.md) for the collaboration-pull model.

## About

**[Cognis Digital](https://cognis.digital)** — Wyoming, USA · *Making Tomorrow Better Today: Advanced Cybersecurity, AI Innovation, and Blockchain Expertise.*
