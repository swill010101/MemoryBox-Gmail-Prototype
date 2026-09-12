"""Synthetic proofs for the I14 Peggy reconstruction preview. No production DB."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from memorybox.ops import i14_peggy_preview as preview
from memorybox.ops.i14_peggy_preview import PreviewError

HASH = "ab" * 32
HASH_B = "cd" * 32


def _eid(n: int) -> str:
    return f"00000000-0000-4000-8000-{n:012d}"


def _payload(**kwargs) -> dict:
    base = {
        "evidence_channel": "email",
        "subject": "Hello",
        "from": "Alice <alice@example.test>",
        "to": ["Bob <bob@example.test>"],
        "sent_at": "2020-01-01T12:00:00+00:00",
        "body_text": "hello there",
        "rfc_message_id": "<one@example.test>",
        "in_reply_to_ids": [],
        "reference_ids": [],
        "thread_id": None,
        "thread_status": "unthreaded",
        "mailbox_skip": "",
        "content_hash": HASH,
        "attachments": [],
        "person_ids": [],
    }
    base.update(kwargs)
    return base


def _msg(n: int, **kwargs) -> dict:
    return preview.message_from_payload(
        evidence_id=_eid(n),
        source_id="11111111-1111-4111-8111-111111111111",
        payload=_payload(**kwargs),
    )


class PeggyPreviewSynthetic(unittest.TestCase):
    def test_full_corpus(self) -> None:
        pack = _build_all_cases()
        self.assertEqual(pack["unexplained"], 0)
        self.assertTrue(pack["completeness_ok"])
        self.assertGreaterEqual(pack["displayed"] + pack["deliberate_duplicates"], pack["eligible"])
        missing = pack["case_missing"]
        self.assertEqual(missing, [], msg=f"missing cases {missing} coverage={pack['case_coverage']}")
        report = preview.counts_report(pack)
        blob = json.dumps(report)
        self.assertNotIn("@", blob)
        self.assertNotIn("alice", blob.lower())
        self.assertNotIn("SECRET", blob)
        html_doc = preview.render_html(pack)
        self.assertIn("accept_thread", html_doc)
        self.assertIn("needs_investigation", html_doc)
        self.assertIn("completeness holds", html_doc)
        self.assertIn("immutable original", html_doc)

    def test_same_subject_does_not_merge_unthreaded(self) -> None:
        a = _msg(1, rfc_message_id=None, message_id="", subject="Picnic", content_hash="33" * 32)
        b = _msg(
            2,
            rfc_message_id=None,
            message_id="",
            subject="Picnic",
            content_hash="44" * 32,
            sent_at="2020-03-01T10:00:00+00:00",
            **{"from": "Carol <carol@example.test>"},
        )
        a["rfc_message_id"] = None
        b["rfc_message_id"] = None
        pack = preview.reconstruct([a, b])
        self.assertEqual(pack["thread_count"], 2)

    def test_spam_excluded_from_eligible(self) -> None:
        good = _msg(1, content_hash="55" * 32)
        spam = _msg(2, mailbox_skip="spam", content_hash="66" * 32, rfc_message_id="<spam@example.test>")
        pack = preview.reconstruct([good, spam])
        self.assertEqual(pack["eligible"], 1)
        self.assertEqual(pack["excluded"], 1)
        self.assertEqual(pack["displayed"], 1)
        self.assertEqual(pack["unexplained"], 0)

    def test_duplicate_hash_omitted(self) -> None:
        a = _msg(1, content_hash=HASH, rfc_message_id="<dup@example.test>")
        b = _msg(
            2,
            content_hash=HASH,
            rfc_message_id="<dup@example.test>",
            sent_at="2020-01-02T12:00:00+00:00",
        )
        pack = preview.reconstruct([a, b])
        self.assertEqual(pack["displayed"], 1)
        self.assertEqual(pack["deliberate_duplicates"], 1)
        self.assertIn("duplicate_across_extracts", pack["threads"][0]["cases"])

    def test_write_gate(self) -> None:
        class _Conn:
            def execute(self, sql, params=None):
                raise AssertionError("should refuse before execute")

        with self.assertRaises(PreviewError) as ctx:
            preview.catalog_execute(_Conn(), "INSERT INTO comms_logical_sources (logical_key) VALUES ('x')")
        self.assertEqual(str(ctx.exception), "persistent_write_refused")

    def test_refuse_memorybox_without_override(self) -> None:
        os.environ.pop("MEMORYBOX_I14_PREVIEW_ALLOW_MEMORYBOX_DB", None)

        class _Cur:
            def fetchone(self):
                return {"d": "memorybox"}

        class _Conn:
            def execute(self, sql, params=None):
                return _Cur()

        with self.assertRaises(PreviewError) as ctx:
            preview.require_dbname(_Conn())
        self.assertEqual(str(ctx.exception), "refused_memorybox_dbname")

    def test_cli_fixture_roundtrip(self) -> None:
        corpus = _all_case_messages()
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "fix.json"
            html_out = Path(tmp) / "preview.html"
            counts = Path(tmp) / "counts.json"
            fixture.write_text(json.dumps(corpus, default=str), encoding="utf-8")
            rc = preview.main(
                ["--fixture-json", str(fixture), "--html-out", str(html_out), "--counts-out", str(counts)]
            )
            self.assertEqual(rc, 0)
            report = json.loads(counts.read_text(encoding="utf-8"))
            preview.assert_counts_only(report)
            self.assertTrue(html_out.exists())
            self.assertIn("I14 Peggy", html_out.read_text(encoding="utf-8"))


def _all_case_messages() -> list[dict]:
    authored = "unique authored line about the picnic plans for saturday"
    long_root = "<longroot@example.test>"
    messages = [
        _msg(
            1,
            rfc_message_id=long_root,
            subject="Long chat",
            body_text=authored,
            sent_at="2020-04-01T10:00:00+00:00",
            content_hash="01" * 32,
        ),
    ]
    prior = authored
    for i in range(2, 9):
        messages.append(
            _msg(
                i,
                rfc_message_id=f"<long{i}@example.test>",
                in_reply_to_ids=[long_root if i == 2 else f"<long{i-1}@example.test>"],
                reference_ids=[long_root],
                subject="Re: Long chat" if i < 5 else "Changed long subject",
                body_text=("On sat alice@example.test wrote:\n" + prior + "\n\n")
                + f"turn {i} still talking",
                sent_at=f"2020-04-01T{10+i:02d}:00:00+00:00",
                content_hash=f"{i:02d}" * 32,
                **{"from": "Bob <bob@example.test>" if i % 2 == 0 else "Alice <alice@example.test>"},
            )
        )
        prior = f"turn {i} still talking"
    messages.append(
        _msg(
            20,
            rfc_message_id="<fwd@example.test>",
            subject="Fwd: tickets",
            body_text="Begin forwarded message:\n\nSee the tickets.",
            sent_at="2020-05-01T10:00:00+00:00",
            content_hash="20" * 32,
            attachments=[{"filename": "t.pdf"}],
        )
    )
    messages.append(
        _msg(
            21,
            rfc_message_id=None,
            message_id="",
            subject="Orphan picnic",
            body_text="are we still on",
            sent_at="2020-05-02T10:00:00+00:00",
            content_hash="21" * 32,
        )
    )
    messages[-1]["rfc_message_id"] = None
    messages.append(
        _msg(
            22,
            rfc_message_id=None,
            message_id="",
            subject="Orphan picnic",
            body_text="different day picnic",
            sent_at="2020-05-03T10:00:00+00:00",
            content_hash="22" * 32,
            **{"from": "Dana <dana@example.test>"},
        )
    )
    messages[-1]["rfc_message_id"] = None
    messages.append(
        _msg(
            30,
            rfc_message_id="<dup@example.test>",
            subject="Same across extracts",
            body_text="payload one",
            content_hash=HASH,
            sent_at="2020-06-01T10:00:00+00:00",
        )
    )
    messages.append(
        _msg(
            31,
            rfc_message_id="<dup@example.test>",
            subject="Same across extracts",
            body_text="payload one",
            content_hash=HASH,
            sent_at="2020-06-01T11:00:00+00:00",
        )
    )
    messages.append(
        _msg(
            40,
            rfc_message_id="<spam1@example.test>",
            mailbox_skip="trash",
            subject="deleted",
            content_hash="40" * 32,
        )
    )
    # RFC cluster with two vendor ids (threader combine warning)
    messages.append(
        _msg(
            50,
            rfc_message_id="<fam@example.test>",
            vendor_thread_id="vendor-a",
            subject="Family note",
            content_hash="50" * 32,
            sent_at="2020-07-01T10:00:00+00:00",
        )
    )
    messages.append(
        _msg(
            51,
            rfc_message_id="<fam2@example.test>",
            in_reply_to_ids=["<fam@example.test>"],
            reference_ids=["<fam@example.test>"],
            vendor_thread_id="vendor-b",
            subject="Re: Family note",
            content_hash="51" * 32,
            sent_at="2020-07-01T11:00:00+00:00",
            **{"from": "Bob <bob@example.test>"},
        )
    )
    return messages


def _build_all_cases() -> dict:
    return preview.reconstruct(_all_case_messages())


class PeggyPreviewCases(unittest.TestCase):
    def test_cases_present(self) -> None:
        pack = _build_all_cases()
        self.assertEqual(pack["case_missing"], [])
        self.assertEqual(pack["unexplained"], 0)
        self.assertGreaterEqual(pack["deliberate_duplicates"], 1)
        self.assertGreaterEqual(pack["excluded"], 1)


if __name__ == "__main__":
    unittest.main()
