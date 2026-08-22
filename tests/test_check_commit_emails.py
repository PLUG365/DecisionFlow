import unittest

from scripts.check_commit_emails import blocked_emails, email_domain


class CommitEmailGuardTests(unittest.TestCase):
    def test_email_domain_is_case_insensitive(self):
        self.assertEqual(email_domain("Name@Gmail.COM"), "gmail.com")

    def test_blocked_emails_finds_consumer_domains(self):
        found = blocked_emails(
            [
                "173816569+minoru365@users.noreply.github.com",
                "person@Gmail.com",
                "geekfujiwara@outlook.com",
                "",
            ]
        )
        self.assertEqual(found, ["person@Gmail.com"])

    def test_blocked_emails_ignores_noreply_and_work_addresses(self):
        self.assertEqual(
            blocked_emails(
                [
                    "copilot@github.com",
                    "96101315+geekfujiwara@users.noreply.github.com",
                    "geekfujiwara@outlook.com",
                ]
            ),
            [],
        )
