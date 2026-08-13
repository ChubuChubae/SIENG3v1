"""Every package must import, and the public API must actually exist.

This catches the worst kind of refactor regression: a file moves, an __init__.py is
left behind, and nobody notices until the GUI is opened.
"""

import importlib
import pkgutil

import pytest

import sieng


def all_module_names():
    """Every module under sieng, minus __main__ which is meant to run as a script."""
    return [
        module.name
        for module in pkgutil.walk_packages(sieng.__path__, "sieng.")
        if not module.name.endswith("__main__")
    ]


def test_package_tree_is_not_empty():
    assert len(all_module_names()) > 30, "package tree is missing, check that __init__.py exists"


@pytest.mark.parametrize("module_name", all_module_names())
def test_every_package_imports(module_name):
    importlib.import_module(module_name)


def test_public_api_exists():
    assert sieng.__version__
    assert sieng.CRYPTO_SUITE.startswith("x25519-mlkem768")

    for name in sieng.__all__:
        assert hasattr(sieng, name), f"__all__ lists {name} but it does not exist"
