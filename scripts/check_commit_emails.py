"""Reject consumer personal emails in git author/committer metadata."""

from __future__ import annotations

import argparse
import subprocess
import sys

BLOCKED_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "icloud.com",
        "me.com",
        "mac.com",
        "yahoo.com",
        "yahoo.co.jp",
    }
)


def email_domain(email: str) -> str:
    if "@" not in email:
        return ""
    return email.rsplit("@", 1)[-1].strip().lower()


def blocked_emails(emails: list[str]) -> list[str]:
    found: set[str] = set()
    for raw in emails:
        email = raw.strip()
        if email and email_domain(email) in BLOCKED_DOMAINS:
            found.add(email)
    return sorted(found)


def _git_output(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def history_emails() -> list[str]:
    # branches/tags only. Backup refs and remotes may still hold pre-rewrite objects.
    return [
        line
        for line in _git_output(["log", "--branches", "--tags", "--format=%ae%n%ce"]).splitlines()
        if line
    ]


def configured_email() -> str:
    result = subprocess.run(
        ["git", "config", "--get", "user.email"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-config",
        action="store_true",
        help="Do not check the current git user.email",
    )
    args = parser.parse_args(argv)

    problems: list[str] = []
    leaked = blocked_emails(history_emails())
    if leaked:
        problems.append("commit history contains blocked personal email domains")

    if not args.skip_config:
        current = configured_email()
        if blocked_emails([current]):
            problems.append(
                "git user.email uses a blocked personal domain; "
                "set this repo to a GitHub noreply address"
            )

    if problems:
        print("Commit email check failed:", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        print(
            "Use an address like <id>+<user>@users.noreply.github.com",
            file=sys.stderr,
        )
        return 1

    print("Commit email check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
