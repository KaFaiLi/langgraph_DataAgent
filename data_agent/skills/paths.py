"""Trusted skill locations for source checkouts and installed distributions."""

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CHECKOUT_ROOT = PACKAGE_ROOT.parent
IS_CHECKOUT = (CHECKOUT_ROOT / "pyproject.toml").is_file() and (CHECKOUT_ROOT / "skills").is_dir()


def default_skills_root() -> Path:
    """Prefer editable repository assets; wheels carry the same files inside the package."""
    return CHECKOUT_ROOT / "skills" if IS_CHECKOUT else PACKAGE_ROOT / "_bundled_skills"


def runtime_root() -> Path:
    """Resolve writable/configuration paths outside site-packages in installed use."""
    return CHECKOUT_ROOT if IS_CHECKOUT else Path.cwd()
