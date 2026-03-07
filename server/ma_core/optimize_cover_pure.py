"""Server wrapper around the packaged optimize-cover implementation."""

from multiarrangement.optimize_cover_pure import *  # noqa: F401,F403


if __name__ == "__main__":
    from multiarrangement.optimize_cover_pure import main

    raise SystemExit(main())
