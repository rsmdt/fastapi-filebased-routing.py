"""Core layer: framework-agnostic file-based routing components.

This layer holds the pipeline (paths -> discovery -> selection -> module loading
-> handler extraction) plus the class-based route API and the middleware runtime.

Layer boundary: nothing in ``core`` may import the ``fastapi`` package or the
sibling ``adapter`` layer. Deep paths under ``core`` are internal and unstable;
the only sanctioned import surface is the package root.
"""
