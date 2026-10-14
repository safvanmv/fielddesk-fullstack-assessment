#!/usr/bin/env python
import os
import sys


def main() -> None:
    if sys.argv[1:2] == ["test"]:
        # Always test against config.settings.test, even where the environment selects local settings
        # (as Docker Compose does). An explicit --settings flag still takes precedence.
        os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.test"
    else:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
