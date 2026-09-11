"""Historian Capture ingest idempotency: DB unique inbound_message_id, not IMAP checkpoint."""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from tests.test_hc_privateemail import FakeIMAP, MAILBOX, TOKEN, _raw_reply


def _hc_db_available() -> bool:
    try:
        from memorybox.db import ping

        ping()
        from memorybox.db import connection

        with connection() as conn:
            conn.execute("SELECT 1 FROM historian_capture_items LIMIT 1")
        return True
    except Exception:
        return False


class HcIngestIdempotentTests(unittest.TestCase):
    def test_unique_index_exists_in_i12_migration(self) -> None:
        sql = (
            Path(__file__).resolve().parents[1]
            / "memorybox"
            / "migrations"
            / "025_historian_capture_i12.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("CREATE UNIQUE INDEX IF NOT EXISTS idx_hc_items_inbound_msg", sql)
        self.assertIn("historian_capture_items (inbound_message_id)", sql)

    @unittest.skipUnless(_hc_db_available(), "Historian Capture Postgres not available")
    def test_checkpoint_reset_does_not_duplicate_db_ingest(self) -> None:
        from memorybox.historian_capture import (
            FakeHistorianEmailAdapter,
            create_campaign,
            get_campaign,
            list_capture_items,
            poll_and_ingest,
            set_email_adapter,
            start_campaign,
            tick_scheduler,
        )
        from memorybox.historian_capture.acceptance import _seed_person
        from memorybox.historian_capture.privateemail import NamecheapPrivateEmailAdapter
        from memorybox.db import connection

        os.environ["MEMORYBOX_HC_EMAIL_PROVIDER"] = "fake"
        set_email_adapter(None)
        tag = f"HC1-{uuid4().hex[:8]}"
        people_id = _seed_person()
        email = f"respondent.{tag.lower()}@example.com"
        fake = FakeHistorianEmailAdapter()
        camp = create_campaign(
            title=f"Idempotent {tag}",
            follow_up_interval_seconds=3600,
            send_thank_you_ack=True,
            respondents=[
                {
                    "people_id": people_id,
                    "display_name_snapshot": f"Peggy {tag}",
                    "contact_route_value": email,
                }
            ],
            questions=[f"What about {tag}?"],
        )
        camp = start_campaign(camp["id"])
        tick_scheduler(adapter=fake)
        camp = get_campaign(camp["id"])
        token = camp["deliveries"][0]["correlation_token"]
        mid = f"<db-dup-{tag}@test>"

        with tempfile_checkpoint() as ckpt:
            raw = _raw_reply(
                message_id=mid,
                to_addr=f"memorybox+hc-{token}@marvinbot.net",
                subject="A MemoryBox question from Tom about Kitchen memories",
                body=f"The Sunday dinner {tag}.",
            )
            imap = FakeIMAP({"INBOX": {7: raw}})
            pe = NamecheapPrivateEmailAdapter(
                {"username": MAILBOX, "password": "x"},
                preserve_root=Path(ckpt).parent / "mail",
            )
            with patch("memorybox.historian_capture.privateemail.open_imap", return_value=imap):
                first = poll_and_ingest(adapter=pe)
                Path(ckpt).unlink(missing_ok=True)
                pe = NamecheapPrivateEmailAdapter(
                    {"username": MAILBOX, "password": "x"},
                    preserve_root=Path(ckpt).parent / "mail",
                )
                second = poll_and_ingest(adapter=pe)

        items = [
            i
            for i in list_capture_items(campaign_id=camp["id"])
            if i.get("inbound_message_id") == mid
        ]
        self.assertGreaterEqual(len(first.get("created") or []), 1)
        self.assertEqual(len(items), 1)
        self.assertTrue(
            (second.get("duplicates") or []) or (second.get("created") or []) == []
        )
        camp = get_campaign(camp["id"])
        thank_yous = camp.get("thank_yous") or []
        self.assertLessEqual(len(thank_yous), 1)
        with connection() as conn:
            n = conn.execute(
                "SELECT COUNT(*) AS n FROM historian_capture_items WHERE inbound_message_id = %s",
                (mid,),
            ).fetchone()["n"]
        self.assertEqual(int(n), 1)


def tempfile_checkpoint():
    import os
    import tempfile
    from contextlib import contextmanager

    @contextmanager
    def _ctx():
        fd, name = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(name)
        old = os.environ.get("MEMORYBOX_HC_IMAP_CHECKPOINT")
        os.environ["MEMORYBOX_HC_IMAP_CHECKPOINT"] = name
        try:
            yield name
        finally:
            if old is None:
                os.environ.pop("MEMORYBOX_HC_IMAP_CHECKPOINT", None)
            else:
                os.environ["MEMORYBOX_HC_IMAP_CHECKPOINT"] = old
            Path(name).unlink(missing_ok=True)

    return _ctx()


if __name__ == "__main__":
    unittest.main()
