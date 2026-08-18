"""In-repo P2-I8 richer-email fixture (EVS intent stand-in; not the staged owner export)."""
from __future__ import annotations

import base64
from email.message import EmailMessage
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

OWNER = "tom.will@memorybox.test"
PEGGY_ADDR = "peggy.george@memorybox.test"
SISTER_ADDR = "sue.will@memorybox.test"
SHARED_ADDR = "shared.family@memorybox.test"
BOT_ADDR = "bot@memorybox.test"
ROOT_ID = "<i8-thread-root@memorybox.test>"
REPLY_ID = "<i8-thread-reply@memorybox.test>"
XMAS_ID = "<i8-xmas-peggy@memorybox.test>"
INLINE_CID = "i8-inline-photo@memorybox.test"


def _mbox_stamp(addr: str, when: str) -> str:
    return f"From {addr} {when}\n"


def build_i8_fixture_bytes(
    *,
    owner: str = OWNER,
    peggy: str = PEGGY_ADDR,
    sister: str = SISTER_ADDR,
    shared: str = SHARED_ADDR,
    bot: str = BOT_ADDR,
) -> bytes:
    peggy_hdr = f"Peggy George <{peggy}>"
    sister_hdr = f"Sue Will <{sister}>"
    owner_hdr = f"Tom Will <{owner}>"
    chunks: list[bytes] = []

    unthreaded = EmailMessage()
    unthreaded["From"] = f"Archive Bot <{bot}>"
    unthreaded["To"] = owner
    unthreaded["Subject"] = "Unthreaded status note"
    unthreaded["Message-ID"] = "<i8-unthreaded@memorybox.test>"
    unthreaded["Date"] = "Mon, 04 Jan 2016 10:00:00 -0600"
    unthreaded.set_content("Valid email with no In-Reply-To, References, or vendor thread id.")
    chunks.append(_mbox_stamp(bot, "Mon Jan 04 10:00:00 2016").encode() + unthreaded.as_bytes())

    same_subject = EmailMessage()
    same_subject["From"] = "other@memorybox.test"
    same_subject["To"] = owner
    same_subject["Subject"] = "Unthreaded status note"
    same_subject["Message-ID"] = "<i8-same-subject-not-a-thread@memorybox.test>"
    same_subject["Date"] = "Tue, 05 Jan 2016 11:00:00 -0600"
    same_subject.set_content(
        "Same subject as another message, but no RFC relationship. Must stay unthreaded."
    )
    chunks.append(
        _mbox_stamp("other@memorybox.test", "Tue Jan 05 11:00:00 2016").encode()
        + same_subject.as_bytes()
    )

    root = EmailMessage()
    root["From"] = owner_hdr
    root["To"] = peggy_hdr
    root["Subject"] = "Alaska packing list"
    root["Message-ID"] = ROOT_ID
    root["Date"] = "Fri, 15 Dec 2017 09:00:00 -0600"
    root["X-GM-THRID"] = "8800112233"
    root.set_content("Peg, draft packing list for the trip. I8 preserves this; I10/I11 do not infer.")
    chunks.append(_mbox_stamp(owner, "Fri Dec 15 09:00:00 2017").encode() + root.as_bytes())

    reply = EmailMessage()
    reply["From"] = peggy_hdr
    reply["To"] = owner_hdr
    reply["Subject"] = "Re: Alaska packing list"
    reply["Message-ID"] = REPLY_ID
    reply["In-Reply-To"] = ROOT_ID
    reply["References"] = ROOT_ID
    reply["Date"] = "Fri, 15 Dec 2017 12:00:00 -0600"
    reply["X-GM-THRID"] = "8800112233"
    reply.set_content("Got it — I'll bring the camera.")
    chunks.append(_mbox_stamp(peggy, "Fri Dec 15 12:00:00 2017").encode() + reply.as_bytes())

    incomplete = EmailMessage()
    incomplete["From"] = sister_hdr
    incomplete["To"] = owner
    incomplete["Subject"] = "Re: something not in this export"
    incomplete["Message-ID"] = "<i8-orphan-reply@memorybox.test>"
    incomplete["In-Reply-To"] = "<missing-parent-not-in-corpus@memorybox.test>"
    incomplete["References"] = "<missing-parent-not-in-corpus@memorybox.test>"
    incomplete["Date"] = "Wed, 20 Jun 2018 08:00:00 -0500"
    incomplete.set_content("Sister reply whose parent is not in the staged corpus.")
    chunks.append(_mbox_stamp(sister, "Wed Jun 20 08:00:00 2018").encode() + incomplete.as_bytes())

    xmas = EmailMessage()
    xmas["From"] = owner_hdr
    xmas["To"] = peggy_hdr
    xmas["Cc"] = sister_hdr
    xmas["Subject"] = "Christmas week photos"
    xmas["Message-ID"] = XMAS_ID
    xmas["Date"] = "Wed, 20 Dec 2017 16:00:00 -0600"
    xmas.set_content("Holiday note with an ordinary (non-inline) attachment.")
    xmas.add_attachment(_PNG, maintype="image", subtype="png", filename="christmas-card.png")
    chunks.append(_mbox_stamp(owner, "Wed Dec 20 16:00:00 2017").encode() + xmas.as_bytes())

    inbound = EmailMessage()
    inbound["From"] = sister_hdr
    inbound["To"] = owner_hdr
    inbound["Subject"] = "Re: Christmas week photos"
    inbound["Message-ID"] = "<i8-sister-xmas-reply@memorybox.test>"
    inbound["In-Reply-To"] = XMAS_ID
    inbound["References"] = XMAS_ID
    inbound["Date"] = "Thu, 21 Dec 2017 09:30:00 -0600"
    inbound.set_content("Sister responding over the holiday window.")
    chunks.append(_mbox_stamp(sister, "Thu Dec 21 09:30:00 2017").encode() + inbound.as_bytes())

    related = MIMEMultipart("related")
    related["From"] = peggy_hdr
    related["To"] = owner
    related["Subject"] = "Inline CID snapshot"
    related["Message-ID"] = "<i8-inline-cid@memorybox.test>"
    related["Date"] = "Sat, 01 Jun 2019 14:00:00 -0500"
    related.attach(MIMEText("See the snapshot below.", "plain"))
    img = MIMEImage(_PNG, _subtype="png")
    img.add_header("Content-ID", f"<{INLINE_CID}>")
    img.add_header("Content-Disposition", "inline", filename="cid-snap.png")
    related.attach(img)
    chunks.append(_mbox_stamp(peggy, "Sat Jun 01 14:00:00 2019").encode() + related.as_bytes())

    html_only = EmailMessage()
    html_only["From"] = peggy_hdr
    html_only["To"] = owner
    html_only["Subject"] = "HTML-only body"
    html_only["Message-ID"] = "<i8-html-only@memorybox.test>"
    html_only["Date"] = "Sun, 02 Jun 2019 10:00:00 -0500"
    html_only.set_content("<p>HTML only holiday leftover</p>", subtype="html")
    chunks.append(_mbox_stamp(peggy, "Sun Jun 02 10:00:00 2019").encode() + html_only.as_bytes())

    shared_msg = EmailMessage()
    shared_msg["From"] = f"Family Shared <{shared}>"
    shared_msg["To"] = owner
    shared_msg["Subject"] = "Shared address ping"
    shared_msg["Message-ID"] = "<i8-shared-addr@memorybox.test>"
    shared_msg["Date"] = "Mon, 03 Jun 2019 11:00:00 -0500"
    shared_msg.set_content("Same address maps to two People — Review, do not merge on display name.")
    chunks.append(_mbox_stamp(shared, "Mon Jun 03 11:00:00 2019").encode() + shared_msg.as_bytes())

    spam = EmailMessage()
    spam["From"] = "promo@spam.test"
    spam["To"] = owner
    spam["Subject"] = "You have won a prize"
    spam["Message-ID"] = "<i8-spam@memorybox.test>"
    spam["Date"] = "Tue, 04 Jun 2019 08:00:00 -0500"
    spam["X-Gmail-Labels"] = "Spam,Unread"
    spam.set_content("Gmail Spam label — skipped on ingest by default.")
    chunks.append(_mbox_stamp("promo@spam.test", "Tue Jun 04 08:00:00 2019").encode() + spam.as_bytes())

    trash = EmailMessage()
    trash["From"] = "old@memorybox.test"
    trash["To"] = owner
    trash["Subject"] = "Deleted draft leftover"
    trash["Message-ID"] = "<i8-trash@memorybox.test>"
    trash["Date"] = "Tue, 04 Jun 2019 09:00:00 -0500"
    trash["X-Gmail-Labels"] = "Trash"
    trash.set_content("Gmail Trash label — skipped on ingest by default.")
    chunks.append(_mbox_stamp("old@memorybox.test", "Tue Jun 04 09:00:00 2019").encode() + trash.as_bytes())

    nul = EmailMessage()
    nul["From"] = bot
    nul["To"] = owner
    nul["Subject"] = "NUL placeholder"
    nul["Message-ID"] = "<i8-nul@memorybox.test>"
    nul["Date"] = "Tue, 04 Jun 2019 10:00:00 -0500"
    nul["X-GM-THRID"] = "8800112299"
    nul.set_content("body placeholder")
    nul_bytes = (
        nul.as_bytes()
        .replace(b"NUL placeholder", b"NUL\x00 in subject")
        .replace(b"body placeholder", b"body\x00nul")
    )
    chunks.append(_mbox_stamp(bot, "Tue Jun 04 10:00:00 2019").encode() + nul_bytes)

    return b"\n".join(chunks)


def fixture_path() -> Path:
    return Path(__file__).resolve().parents[1] / "_fixtures" / "i8_richer_email.mbox"


def write_i8_fixture(path: Path | None = None, **addrs: str) -> Path:
    dest = path or fixture_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(build_i8_fixture_bytes(**addrs))
    return dest
