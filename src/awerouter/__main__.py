"""`python -m awerouter` == the `awerouter` console script (used by
`serve --background` to spawn the daemon under the running interpreter)."""

from awerouter.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
