# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a general-purpose workspace for running Claude Code to perform ad-hoc tasks, not tied to any specific project.

## Environment

- Python with uv for package management
- Virtual environment: `.venv/`
- Temporary files: `tmp/`

## Usage

- 安装 Python 包时，使用 `uv add <package>` 添加依赖（会自动更新 pyproject.toml 并安装）
- 禁止使用 `uv pip install`，因为它不会更新 pyproject.toml
- 运行 Python 脚本时，使用 `uv run python <script.py>`
