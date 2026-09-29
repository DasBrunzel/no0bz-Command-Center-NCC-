from __future__ import annotations

import html
from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from ncc.config import ROOT

router = APIRouter()


def changelog_text() -> str:
    return (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")


@router.get("/api/changelog")
async def changelog_json() -> dict[str, Any]:
    text = changelog_text()
    return {"markdown": text, "lines": text.splitlines()}


@router.get("/changelog", response_class=HTMLResponse)
async def changelog_page() -> str:
    safe = html.escape(changelog_text())
    return f"<!doctype html><meta charset='utf-8'><title>NCC Changelog</title><style>body{{max-width:900px;margin:3rem auto;padding:0 1rem;background:#071018;color:#d7f9ff;font:16px system-ui}}pre{{white-space:pre-wrap}}</style><h1>Changelog</h1><pre>{safe}</pre>"

