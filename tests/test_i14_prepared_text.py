"""I14 prepared authored-text: quote history vs forwards vs signatures."""
from __future__ import annotations

import unittest

from memorybox.ops.i14_prepared_text import prepare_message_text, classify_residue
from memorybox.ops import i14_peggy_preview as preview
from memorybox.ops import i14_thread_review as review


TOM = "tom@example.test"
PEG = "peggy@example.test"
PRIOR = (
    "Pegs,\n"
    "Just wanted to let you know that dad's financial status is holding up fine.\n"
    "Go Cards!\n"
    "Bro"
)
PEGGY_NEW = (
    "I know you're doing an outstanding job with all.\n"
    "You working entire weekend???  My luv to all,  Pegs"
)
HOTMAIL_TAIL = (
    "\n\nDate: Thu, 29 Sep 2011 10:01:58 -0500\n"
    "Subject: Stuff\n"
    f"From: {TOM}\n"
    f"To: {PEG}\n\n"
    f"{PRIOR}\n"
)


class PreparedTextCleaning(unittest.TestCase):
    def test_hotmail_date_subject_from_to_removed(self) -> None:
        raw = PEGGY_NEW + HOTMAIL_TAIL
        prep = prepare_message_text(raw, subject="RE: Stuff")
        self.assertEqual(prep.method, "hotmail_date_subject_from_to")
        self.assertTrue(prep.quote_history_removed)
        self.assertIn("outstanding job", prep.authored)
        self.assertNotIn("Date: Thu, 29 Sep 2011", prep.authored)
        self.assertNotIn("financial status", prep.authored)
        self.assertNotIn("Go Cards", prep.authored)
        self.assertIsNone(classify_residue(prep.authored))

    def test_on_wrote_removed_preserves_lead(self) -> None:
        raw = "Thanks for the update.\n\nOn Mon, Jan 2, 2012 at 3:04 PM, Tom Example <tom@example.test> wrote:\nhello yesterday\n"
        prep = prepare_message_text(raw, subject="Re: hello")
        self.assertEqual(prep.method, "on_wrote")
        self.assertEqual(prep.authored, "Thanks for the update.")
        self.assertNotIn("hello yesterday", prep.authored)

    def test_inline_replies_kept(self) -> None:
        raw = (
            "I agree with the plan.\n"
            "> we should wait until Tuesday\n"
            "> unless the shop is closed\n"
            "Also bring the keys.\n"
        )
        prep = prepare_message_text(raw, subject="Re: plan")
        self.assertIn("I agree with the plan.", prep.authored)
        self.assertIn("Also bring the keys.", prep.authored)
        self.assertNotIn("wait until Tuesday", prep.authored)

    def test_forward_not_treated_as_reply_history(self) -> None:
        raw = (
            "See below.\n\n"
            "Begin forwarded message:\n\n"
            "From: Airline <desk@example.test>\n"
            "Subject: itinerary\n\n"
            "Your flight confirmation is attached.\n"
        )
        prep = prepare_message_text(raw, subject="FW: itinerary")
        self.assertTrue(prep.method.startswith("explicit_forward"))
        self.assertEqual(prep.authored, "See below.")
        self.assertIn("flight confirmation", prep.forward_block)
        self.assertIn("Begin forwarded message", raw)

    def test_signature_separate_from_quotes(self) -> None:
        raw = "Hello there.\n\n-- \nSent from my iPhone"
        prep = prepare_message_text(raw, subject="Hi")
        self.assertTrue(prep.signature_removed or prep.list_footer_removed)
        self.assertIn("Hello there.", prep.authored)
        self.assertNotIn("Sent from my iPhone", prep.authored)
        self.assertFalse(prep.quote_history_removed)

    def test_original_message_header_removed(self) -> None:
        raw = "Will do.\n\n-----Original Message-----\nFrom: tom@example.test\nhello yesterday\n"
        prep = prepare_message_text(raw, subject="Re: hello")
        self.assertEqual(prep.method, "original_message")
        self.assertEqual(prep.authored, "Will do.")
        self.assertNotIn("hello yesterday", prep.authored)

    def test_bottom_posted_on_wrote_keeps_new_text(self) -> None:
        prior = "unique authored line about the picnic plans for saturday"
        raw = f"On sat alice@example.test wrote:\n{prior}\n\nturn 2 still talking"
        prep = prepare_message_text(raw, subject="Re: Long chat", prior_authored=[prior])
        self.assertIn("turn 2 still talking", prep.authored)
        self.assertNotIn("picnic plans", prep.authored)

    def test_original_input_unchanged(self) -> None:
        raw = PEGGY_NEW + HOTMAIL_TAIL
        snapshot = raw
        prepare_message_text(raw, subject="RE: Stuff")
        self.assertEqual(raw, snapshot)

    def test_t0624_eight_messages_no_repeat(self) -> None:
        ledger = review.IdentityLedger(focal_person_id="person-peggy")
        review.add_confirmed_address(ledger, address=PEG, person_id="person-peggy", label="Peggy Example")
        review.add_confirmed_address(ledger, address=TOM, person_id="person-tom", label="Tom Example")
        bodies = []
        tom_turn = PRIOR
        peg_turn = PEGGY_NEW
        for i in range(1, 9):
            if i % 2 == 1:
                subj = "Stuff" if i == 1 else "Re: Stuff"
                body = tom_turn if i == 1 else tom_turn + (
                    f"\n\nOn a previous day {PEG} wrote:\n" + peg_turn if i > 1 else ""
                )
                frm = f"Tom <{TOM}>"
                to = [f"Peggy <{PEG}>"]
            else:
                subj = "RE: Stuff"
                body = peg_turn + HOTMAIL_TAIL.replace(PRIOR, tom_turn)
                frm = f"Peg Legg <{PEG}>"
                to = [f"Tom <{TOM}>"]
            bodies.append((i, subj, body, frm, to))
        messages = []
        for i, subj, body, frm, to in bodies:
            messages.append(
                preview.message_from_payload(
                    evidence_id=f"00000000-0000-4000-8000-{i:012d}",
                    source_id="11111111-1111-4111-8111-111111111111",
                    payload={
                        "evidence_channel": "email",
                        "subject": subj,
                        "from": frm,
                        "to": to,
                        "from_parsed": [
                            {
                                "display_name": frm.split("<")[0].strip(),
                                "address": PEG if i % 2 == 0 else TOM,
                                "normalized": PEG if i % 2 == 0 else TOM,
                            }
                        ],
                        "to_parsed": [
                            {
                                "display_name": "x",
                                "address": TOM if i % 2 == 0 else PEG,
                                "normalized": TOM if i % 2 == 0 else PEG,
                            }
                        ],
                        "sent_at": f"2011-09-29T1{i}:00:00+00:00",
                        "body_text": body,
                        "rfc_message_id": f"<m{i}@example.test>",
                        "in_reply_to_ids": [f"<m{i-1}@example.test>"] if i > 1 else [],
                        "reference_ids": [f"<m1@example.test>"] if i > 1 else [],
                        "content_hash": f"{i:02d}" * 32,
                        "mailbox_skip": "",
                    },
                )
            )
        pack = preview.reconstruct(messages, ledger=ledger)
        self.assertEqual(pack["displayed"], 8)
        self.assertEqual(pack["unexplained"], 0)
        self.assertEqual(pack["thread_count"], 1)
        thread = pack["threads"][0]
        self.assertEqual(len(thread["messages"]), 8)
        peggy_voice = []
        for i, msg in enumerate(thread["messages"], start=1):
            cleaned = msg["cleaned_body"]
            self.assertNotIn("Date: Thu, 29 Sep 2011", cleaned)
            self.assertNotIn("Subject: Stuff\nFrom:", cleaned)
            original = msg.get("raw_body") or ""
            self.assertTrue(original)
            if i % 2 == 0:
                self.assertIn("Date: Thu, 29 Sep 2011", original)
                self.assertTrue(msg.get("voice_corpus"))
                self.assertIn("outstanding job", cleaned)
                self.assertNotIn("financial status", cleaned)
                rendered = review.format_thread_txt(thread)
                self.assertIn("outstanding job", rendered)
                self.assertNotRegex(
                    rendered,
                    r"Cleaned authored text:\n.*Date: Thu, 29 Sep 2011",
                )
                peggy_voice.append(cleaned)
            else:
                self.assertFalse(msg.get("voice_corpus"))
        self.assertEqual(len(peggy_voice), 4)
        self.assertTrue(all("financial status" not in v for v in peggy_voice))


class PreparedPolicyRegressions(unittest.TestCase):
    def test_utc_offset_sort_puts_earlier_instant_first(self) -> None:
        early = {"timestamp": "2025-12-18T14:57:13+00:00", "evidence_id": "b"}
        late = {"timestamp": "2025-12-18T09:13:25-06:00", "evidence_id": "a"}
        ordered = sorted([late, early], key=review.message_sort_key)
        self.assertEqual([m["evidence_id"] for m in ordered], ["b", "a"])
        lex = sorted([late, early], key=review.string_sort_key)
        self.assertEqual([m["evidence_id"] for m in lex], ["a", "b"])

    def test_missing_timestamp_sorts_last(self) -> None:
        missing = {"timestamp": "", "evidence_id": "z"}
        present = {"timestamp": "2025-12-18T08:00:00-06:00", "evidence_id": "a"}
        ordered = sorted([missing, present], key=review.message_sort_key)
        self.assertEqual([m["evidence_id"] for m in ordered], ["a", "z"])

    def test_forward_wrapper_still_strips_on_wrote(self) -> None:
        raw = (
            "I am thinking of you.\n\n"
            "On Thu, Dec 18, 2025 at 8:24 AM Person Example <a@example.test> wrote:\n"
            "earlier condolence that is already in the thread\n\n"
            "Begin forwarded message:\n\n"
            + ("relayed chain already represented separately in an earlier evidence message. " * 4)
        )
        chain = "relayed chain already represented separately in an earlier evidence message. " * 4
        prep = prepare_message_text(
            raw,
            subject="Fwd: news",
            prior_authored=[chain],
        )
        self.assertIn("I am thinking of you.", prep.authored)
        self.assertNotIn("wrote:", prep.authored)
        self.assertEqual(prep.forward_omitted, "duplicate_of_thread_message")
        raw = (
            "Thank you for writing.\n\n"
            "On Thu, Dec 18, 2025 at 8:24 AM Person Example\n"
            "<person@example.test> wrote:\n"
            "the previous condolence text\n"
        )
        prep = prepare_message_text(raw, subject="Re: news")
        self.assertIn("Thank you for writing.", prep.authored)
        self.assertNotIn("wrote:", prep.authored)
        self.assertNotIn("previous condolence", prep.authored)

    def test_fwd_subject_with_reply_history_is_not_forward_block(self) -> None:
        prior = "original condolence from the first sender in this thread " * 2
        raw = f"My new reply.\n\nOn Thu, Dec 18, 2025 at 8:24 AM A <a@example.test> wrote:\n{prior}\n"
        prep = prepare_message_text(raw, subject="Fwd: family news", prior_authored=[prior])
        self.assertEqual(prep.forward_block, "")
        self.assertIn("My new reply.", prep.authored)
        self.assertNotIn("original condolence", prep.authored)

    def test_new_forward_kept_when_not_in_thread(self) -> None:
        raw = (
            "See below.\n\nBegin forwarded message:\n\n"
            "From: Desk <desk@example.test>\n"
            "Your flight AA123 confirmation number ABCDE is attached.\n"
        )
        prep = prepare_message_text(raw, subject="Fwd: itinerary")
        self.assertIn("See below.", prep.authored)
        self.assertIn("AA123", prep.forward_block)
        self.assertIn("ABCDE", prep.forward_block)

    def test_duplicate_forward_omitted_when_original_already_in_thread(self) -> None:
        original = "Southwest Rapid Rewards program policy announcement body " * 3
        raw = f"Big changes.\n\nBegin forwarded message:\n\n{original}"
        prep = prepare_message_text(raw, subject="Fwd: policy", prior_authored=[original])
        self.assertEqual(prep.forward_block, "")
        self.assertEqual(prep.forward_omitted, "duplicate_of_thread_message")
        self.assertIn("Big changes", prep.authored)

    def test_southwest_marketing_forward_stripped_and_suppressed(self) -> None:
        raw = (
            "Big changes.\n\nBegin forwarded message:\n\n"
            "Rapid Rewards policy update. Buy points today.\n"
            "https://email.southwest.com/click?utm_source=blast&unsubscribe=1\n"
            "Log in to your account https://southwest.com/login\n"
            "To unsubscribe click here. Privacy policy. Terms of carriage.\n"
        )
        msg = {
            "subject": "Fwd: Rapid Rewards",
            "raw_body": raw,
            "cleaned_body": "Big changes.",
            "forward_block": raw.split("Begin forwarded message:")[-1],
            "from_handle": "tom@example.test",
        }
        cls = review.classify_commercial(msg)
        self.assertEqual(cls["commercial_class"], "commercial_suppress")
        # Marketing copy may say "itinerary" / "check-in" without a real trip.
        noisy = dict(msg)
        noisy["raw_body"] = raw + "\nSee the itinerary online. Check-In now.\n"
        self.assertEqual(review.classify_commercial(noisy)["commercial_class"], "commercial_suppress")
        prep = prepare_message_text(raw, subject="Fwd: Rapid Rewards")
        self.assertIn("Big changes", prep.authored)
        self.assertNotIn("http", prep.authored)
        self.assertNotIn("utm_", prep.forward_block)
        row = dict(msg)
        row["cleaned_body"] = prep.authored
        row["forward_block"] = prep.forward_block
        row.update(review.classify_commercial(row))
        if row["commercial_class"] == "commercial_suppress":
            row["forward_block"] = ""
        self.assertEqual(row["forward_block"], "")
        self.assertNotIn("unsubscribe", row["cleaned_body"].lower())

    def test_itinerary_forward_keeps_facts_without_urls(self) -> None:
        raw = (
            "Our trip.\n\nBegin forwarded message:\n\n"
            "Your itinerary: flight AA123 confirmation number XYZ99 May 12.\n"
            "https://airline.example.test/checkin?utm_source=mail\n"
            "To unsubscribe click here.\n"
        )
        prep = prepare_message_text(raw, subject="Fwd: itinerary")
        cls = review.classify_commercial(
            {
                "subject": "Fwd: itinerary",
                "cleaned_body": prep.authored,
                "forward_block": prep.forward_block,
                "raw_body": raw,
            }
        )
        self.assertEqual(cls["commercial_class"], "commercial_retain")
        self.assertIn("AA123", prep.forward_block)
        self.assertIn("XYZ99", prep.forward_block)
        self.assertNotIn("http", prep.forward_block)
        self.assertNotIn("utm_", prep.forward_block)

    def test_reconstruct_orders_mixed_offsets(self) -> None:
        ledger = review.IdentityLedger(focal_person_id="person-sue")
        review.add_confirmed_address(ledger, address="sue@example.test", person_id="person-sue", label="Sue Example")
        review.add_confirmed_address(ledger, address="tom@example.test", person_id="person-tom", label="Tom Example")
        a = preview.message_from_payload(
            evidence_id="00000000-0000-4000-8000-000000000001",
            source_id="11111111-1111-4111-8111-111111111111",
            payload={
                "evidence_channel": "email",
                "subject": "Re: news",
                "from": "Tom <tom@example.test>",
                "to": ["Sue <sue@example.test>"],
                "from_parsed": [{"display_name": "Tom", "address": "tom@example.test", "normalized": "tom@example.test"}],
                "to_parsed": [{"display_name": "Sue", "address": "sue@example.test", "normalized": "sue@example.test"}],
                "sent_at": "2025-12-18T09:13:25-06:00",
                "body_text": "Later reply at 09:13.",
                "rfc_message_id": "<later@example.test>",
                "in_reply_to_ids": ["<early@example.test>"],
                "content_hash": "11" * 32,
            },
        )
        b = preview.message_from_payload(
            evidence_id="00000000-0000-4000-8000-000000000002",
            source_id="11111111-1111-4111-8111-111111111111",
            payload={
                "evidence_channel": "email",
                "subject": "Re: news",
                "from": "Sue <sue@example.test>",
                "to": ["Tom <tom@example.test>"],
                "from_parsed": [{"display_name": "Sue", "address": "sue@example.test", "normalized": "sue@example.test"}],
                "to_parsed": [{"display_name": "Tom", "address": "tom@example.test", "normalized": "tom@example.test"}],
                "sent_at": "2025-12-18T14:57:13+00:00",
                "body_text": "Earlier reply at 08:57.",
                "rfc_message_id": "<early@example.test>",
                "content_hash": "22" * 32,
            },
        )
        pack = preview.reconstruct([a, b], ledger=ledger)
        msgs = pack["threads"][0]["messages"]
        self.assertEqual([m["cleaned_body"] for m in msgs], ["Earlier reply at 08:57.", "Later reply at 09:13."])

    def test_original_unchanged_when_sanitizing(self) -> None:
        raw = "Hi\n\nBegin forwarded message:\n\nhttps://click.example.test/x?utm_source=1\n"
        snapshot = raw
        prepare_message_text(raw, subject="Fwd: x")
        self.assertEqual(raw, snapshot)


if __name__ == "__main__":
    unittest.main()
