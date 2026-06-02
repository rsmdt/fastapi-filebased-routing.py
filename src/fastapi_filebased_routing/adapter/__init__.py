"""Adapter layer: the thin FastAPI-facing glue over the core pipeline.

This is the ONLY layer that imports the ``fastapi`` package. It depends on
``core`` exclusively through public seams (never private names). Deep paths
under ``adapter`` are internal and unstable; the only sanctioned import surface
is the package root.
"""
