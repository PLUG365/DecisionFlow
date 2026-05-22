import unittest

from scripts.backfill_application_share_for_participants import build_application_grant_payload


class ApplicationShareBackfillTests(unittest.TestCase):
    def test_builds_application_grant_payload_with_read_and_appendto(self):
        payload = build_application_grant_payload("ds", "application-id", "user-id")

        self.assertEqual(payload["Target"]["@odata.type"], "Microsoft.Dynamics.CRM.ds_application")
        self.assertEqual(payload["Target"]["ds_applicationid"], "application-id")
        self.assertEqual(payload["PrincipalAccess"]["Principal"]["@odata.type"], "Microsoft.Dynamics.CRM.systemuser")
        self.assertEqual(payload["PrincipalAccess"]["Principal"]["systemuserid"], "user-id")
        self.assertEqual(payload["PrincipalAccess"]["AccessMask"], "ReadAccess,AppendToAccess")


if __name__ == "__main__":
    unittest.main()