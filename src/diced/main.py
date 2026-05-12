"""Thin package entry point for launching the GUI."""

from .gui import launch


def main() -> None:
    """Run the desktop application."""

    launch()


if __name__ == "__main__":
    main()