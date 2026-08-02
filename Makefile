# APEXFIN Makefile —— demo 的稳定入口（docs/CLI_CONTRACT.md 五）
#
# 目标与 CLI_CONTRACT §五 一致；demo / demo-stale 前置 uv sync --frozen，
# 保证干净 clone 后首次 make 即依赖就绪。apexfin 以 .venv/bin/apexfin 调用
#（等价契约中的 `apexfin`，只是显式使用 uv 创建的 venv 内命令）。
# test/lint/typecheck/sprite 需要 dev 工具，前置 `uv sync --frozen --extra dev`
#（uv sync 默认只装运行依赖，pytest/ruff/mypy 在 [project.optional-dependencies].dev）。
#
# 退出码契约：demo=0 / demo-stale=4 / test=0 / lint=0 / typecheck=0 / sprite=0

APEXFIN := .venv/bin/apexfin
PYTHON  := .venv/bin/python

.PHONY: demo demo-stale test lint typecheck sprite

## 离线 fixture 跑通端到端，生成 dist/index.html，退出码 0
demo:
	uv sync --frozen
	$(APEXFIN) init
	$(APEXFIN) run daily --fixture-pack fresh

## 切换 stale fixture，新鲜度闸门 BLOCKED，退出码必须为 4（CI 回归断言）
demo-stale:
	uv sync --frozen
	$(APEXFIN) run daily --fixture-pack stale

test:
	uv sync --frozen --extra dev
	$(PYTHON) -m pytest -q

lint:
	uv sync --frozen --extra dev
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

typecheck:
	uv sync --frozen --extra dev
	$(PYTHON) -m mypy src/apexfin

sprite:
	uv sync --frozen --extra dev
	$(PYTHON) tools/build_sprite.py
