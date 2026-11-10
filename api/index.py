# (c) 2026 Tanishk Kamra | All rights reserved | github.com/TanishkKamra/hceson | tkp-2603f7a67b-725fbf󠁻󠁴󠁫󠁰󠀭󠀲󠀶󠀰󠀳󠁦󠀷󠁡󠀶󠀷󠁢󠀭󠀷󠀲󠀵󠁦󠁢󠁦󠁽
"""Vercel serverless entry point: exposes the FastAPI app from backend/."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.main import app  # noqa: E402,F401
