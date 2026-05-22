import unittest

from scripts.backfill_decision_read_access import build_decision_grant_payload


class DecisionAccessBackfillTests(unittest.TestCase):
    def test_builds_raw_dataverse_grant_access_payload_for_decision_read(self):
        payload = build_decision_grant_payload("ds", "decision-id", "user-id")

        self.assertEqual(payload["Target"]["@odata.type"], "Microsoft.Dynamics.CRM.ds_decision")
        self.assertEqual(payload["Target"]["ds_decisionid"], "decision-id")
        self.assertEqual(payload["PrincipalAccess"]["Principal"]["@odata.type"], "Microsoft.Dynamics.CRM.systemuser")
        self.assertEqual(payload["PrincipalAccess"]["Principal"]["systemuserid"], "user-id")
        self.assertEqual(payload["PrincipalAccess"]["AccessMask"], "ReadAccess")


if __name__ == "__main__":
    unittest.main()