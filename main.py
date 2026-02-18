#!/usr/bin/env python3
from viewer.pyside.bootstrap_env import prepare_qt_runtime_env


def main() -> int:
    prepare_qt_runtime_env()
    from viewer.pyside import shell

    return shell.main()


if __name__ == "__main__":
    raise SystemExit(main())
