"""Smoke tests to verify basic package structure and imports."""

import fastapi_filebased_routing


def test_package_imports():
    """Verify the package can be imported."""
    assert fastapi_filebased_routing is not None


def test_package_has_version():
    """Verify the package exposes a version string."""
    assert hasattr(fastapi_filebased_routing, "__version__")
    assert isinstance(fastapi_filebased_routing.__version__, str)
    assert len(fastapi_filebased_routing.__version__) > 0


def test_version_format():
    """Verify version follows semantic versioning format."""
    version = fastapi_filebased_routing.__version__
    parts = version.split(".")
    assert len(parts) >= 3, "Version should have at least major.minor.patch"
    assert parts[0].isdigit(), "Major version should be numeric"
    assert parts[1].isdigit(), "Minor version should be numeric"
