"""Entry point — `asher` CLI command and `python -m asher`."""

from .app import AsherApp


def main() -> None:
    AsherApp().run()


if __name__ == "__main__":
    main()
