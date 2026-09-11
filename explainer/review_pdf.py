#!/usr/bin/env python3
"""Render every page of the explainer PDF to PNG and build one review sheet.

    python3 review_pdf.py [pdf] [outdir]
"""
from __future__ import annotations

import sys
from pathlib import Path

import pymupdf
from PIL import Image

pdf = Path(sys.argv[1] if len(sys.argv) > 1 else "/home/ubuntu/sf-ops/jimsky-voice/dist/JIMSKY-STUDIO.pdf")
out = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/deckpages")
out.mkdir(parents=True, exist_ok=True)
for old in out.glob("*.png"):
    old.unlink()

doc = pymupdf.open(pdf)
pages = []
for i, page in enumerate(doc):
    p = out / f"page-{i + 1:02d}.png"
    page.get_pixmap(dpi=68).save(str(p))
    pages.append(p)
print(f"  {doc.page_count} pages rendered at 68 dpi -> {out}")

ims = [Image.open(p).convert("RGB") for p in pages]
w = 700
h = int(w * ims[0].height / ims[0].width)
cols = 5
rows = (len(ims) + cols - 1) // cols
sheet = Image.new("RGB", (w * cols + 8 * (cols + 1), h * rows + 8 * (rows + 1)), (18, 20, 26))
for i, im in enumerate(ims):
    sheet.paste(im.resize((w, h), Image.LANCZOS), (8 + (i % cols) * (w + 8), 8 + (i // cols) * (h + 8)))
sheet_path = out / "review-sheet.png"
sheet.save(sheet_path)
print(f"  review sheet: {sheet_path}  {sheet.size}  ({len(ims)} pages, {cols} per row)")
