"""Source adapter registry with auto-discovery.

Any module in this package named *_source.py that defines a class
inheriting from SourceAdapter is automatically registered.

Usage:
    from sources import get_all_sources, get_source

    # All registered adapters
    for adapter in get_all_sources():
        sessions = adapter.collect(target_date)

    # Specific adapter by name
    grok = get_source("grok")
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import SourceAdapter

_registry: dict[str, SourceAdapter] = {}
_discovered = False


def _discover_sources() -> None:
    """Auto-discover *_source.py modules and register their adapters."""
    global _discovered
    if _discovered:
        return

    from .base import SourceAdapter as _Base

    package_dir = Path(__file__).parent
    for module_info in pkgutil.iter_modules([str(package_dir)]):
        if not module_info.name.endswith("_source"):
            continue
        module = importlib.import_module(f".{module_info.name}", package=__package__)
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, _Base)
                and attr is not _Base
                and attr.name  # must have a name set
            ):
                try:
                    _registry[attr.name] = attr()
                except Exception as exc:
                    import sys
                    print(
                        f"[sources] Warning: failed to instantiate "
                        f"'{attr.name}': {exc}",
                        file=sys.stderr,
                    )

    _discovered = True


def get_all_sources() -> list[SourceAdapter]:
    """Return all registered source adapters."""
    _discover_sources()
    return list(_registry.values())


def get_source(name: str) -> SourceAdapter | None:
    """Return a specific source adapter by name, or None."""
    _discover_sources()
    return _registry.get(name)


def list_source_names() -> list[str]:
    """Return names of all registered sources."""
    _discover_sources()
    return list(_registry.keys())
