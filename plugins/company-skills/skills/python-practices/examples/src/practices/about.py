"""The package's version, read from its installed metadata."""

from importlib.metadata import version


def package_version() -> str:
    return version("practices")


def main() -> None:
    """Print the version. [project.scripts] installs this as practices-version."""
    print(f"practices {package_version()}")
