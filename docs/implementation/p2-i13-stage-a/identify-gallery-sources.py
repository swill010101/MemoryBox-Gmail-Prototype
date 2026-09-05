"""Read-only lookup of HVRT appearance IDs supplied by Tom. No MB imports or writes."""
import json
import os
from pathlib import Path
from uuid import UUID
import psycopg
from psycopg.rows import dict_row

# Exact rendered HVRT card IDs supplied during this pilot, including known controls.
IDS = """
f46ec430-777e-4f13-8cae-fc5b85b85733
ec512fc5-153a-4c31-9e31-45d1305ad8de
d5d33a17-9da5-4337-ae39-e06e29b45e1b
b87e656b-f844-41e9-bcf3-6b1b5768f088
691fa3b4-ff3b-4551-b24c-8e1be9b1c3e3
f66a9dd4-ce46-4221-b1cc-2dad2680447d
bbba91bb-a2a5-4519-98fd-367d78dec0aa
109cf247-cc8e-4920-b210-6f4dcba8ae2d
8029893a-fc92-47e7-a612-d7f64bf65f97
df10ac70-fd04-410e-afca-bd81ef5eff13
6f25e425-ac78-41e1-8b84-2241db7f00f8
0587481b-ddf2-422a-8eed-1275b0c0cc5e
44abca59-2ac0-48cf-8830-8121f5d125bf
e1307e2e-c7e5-4464-8334-a4fd209b2240
010e742d-2e3c-4b52-a560-840b0970666e
97a0f848-d83b-4691-bbc3-182557996744
bc041a7c-03a3-4f11-b109-d9254b38d8e5
199e0a88-32af-4bff-8f78-87ab7ad61369
4f05e8f3-de8b-42a5-8a2b-d6ccef2685b4
4a63fa54-bc15-4aff-9d18-67b852abceba
7812d337-4f79-4538-971f-b3cd0d42d77e
25b574b9-23a5-482d-8421-8d69e751b69e
0ef7a2bb-9b55-45dd-8950-52357b6f40c8
723f8bde-5c9f-4af1-888a-5e7413cf37fd
4fdecb90-e6af-48fb-8022-890611d0b575
a9ba58bc-2378-401a-ae60-99b83defe4a7
84bf1f3d-2729-4fd2-8193-a2970d4c3a61
c479b3b0-c7f9-40d9-811f-36ea2c9f01a5
4be34568-1f0a-4a4b-8bc2-32556e037242
e76f16eb-7bc7-42da-815d-b2be934800f8
6f9488af-e453-4e7d-9083-cf5165365ad3
75d45fa0-fc95-4b16-8b42-e6085ee242b8
6e872166-dcee-4274-bd64-c22657e23c2a
33ca644e-be4d-44e5-a93b-6c73c35c22f5
2bce4639-e536-4ed5-8768-d4872824f38c
3fbe907d-24e4-4e9c-9067-8e72df70d409
1e34d6dd-d574-4ee8-b8bc-4ba0b5c81078
4cbeb4df-99f9-4caf-a882-8787ff8c0fe0
052b4858-3a6e-449d-89f3-4ab169da49cb
34d450ac-bac0-43ac-80f7-f95adb43d066
0d35459b-bc55-4c23-9fb9-50fae49fb7d6
390ff739-aa61-4396-ab4d-36e3b5f5a3b3
59532ab1-e74a-432d-9baf-8b3f34c6c476
4bddb7e4-8eec-4da5-bc97-29893c1ddc52
d289f38b-a494-43ce-bb8a-baa5a878b4ea
1113ac68-c9ee-40a0-8877-3b1b5f6d1533
6924307e-7aae-4c5d-a7bc-f508086c8079
""".split()


def summarize(rows, sources):
    manifest = {(s["provider_key"], s["video_external_id"]): s for s in sources}
    grouped = {}
    matched = set()
    for row in rows:
        r = dict(row)
        mid = str(r["id"])
        if mid not in IDS or r["video_provider_key"] != "hvrt":
            raise ValueError("Unexpected result outside approved lookup")
        matched.add(mid)
        key = (r["video_provider_key"], r["video_external_id"])
        source = manifest.get(key)
        if key not in grouped:
            grouped[key] = dict(provider=key[0],source_id=key[1],in_manifest=source is not None,
                manifest_filename=source.get("relative_path") if source else None,
                duration_sec=source.get("duration_sec") if source else None,moments=[])
        grouped[key]["moments"].append(r)
    return dict(requested_card_ids=len(IDS), matched_card_ids=len(matched),
                unmatched_card_ids=[i for i in IDS if i not in matched], sources=list(grouped.values()))


def main():
    if len(IDS) > 64 or len(set(IDS)) != len(IDS):
        raise ValueError("Invalid fixed scope")
    ids = [UUID(i) for i in IDS]
    sources=json.loads(Path(__file__).with_name("bounded-manifest-proposal.json").read_text(encoding="utf-8"))["manifest"]["sources"]
    with psycopg.connect(os.environ["MEMORYBOX_DATABASE_URL"],connect_timeout=5,
            options="-c default_transaction_read_only=on -c statement_timeout=20000 -c lock_timeout=3000",
            row_factory=dict_row) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        snapshot=conn.execute("SELECT current_database() AS database, transaction_timestamp() AS captured_at, current_setting('transaction_read_only') AS read_only, current_setting('transaction_isolation') AS isolation").fetchone()
        rows=conn.execute("""
            SELECT id::text, video_provider_key, video_external_id, person_id::text,
                   start_sec, end_sec, method, status, authority, confirmation_state,
                   processing_run_id::text, model_version
            FROM public.face_appearance_moments
            WHERE id = ANY(%s::uuid[]) AND video_provider_key = 'hvrt'
            ORDER BY video_external_id, start_sec, id
            LIMIT 64
        """,(ids,)).fetchall()
    result=summarize(rows,sources)
    result["snapshot"]=snapshot
    result["limits"]=["Only the supplied rendered HVRT IDs; not a fresh Gallery capture or a source-wide inventory",
        "Unmatched IDs need investigation; absence here is not deletion proof",
        "Manifest membership is not processing authorization; no filesystem scan, media decode, service start or DB write"]
    print(json.dumps(result,default=str,indent=2))


if __name__ == "__main__":
    try: main()
    except Exception as exc:
        print(json.dumps(dict(ok=False,error_type=type(exc).__name__,message="Read-only lookup failed. Check configured environment/schema; do not share credentials. No automatic retry.")))
        raise SystemExit(2)
