# TitaNet-Large public threshold calibration

The bounded pilot uses a frozen abstention-first policy: a cosine score below `0.30` is `no_match`; `0.30` through below `0.45` is `uncertain`; `0.45` or greater is `match`.

This was derived without private media. The pinned TitaNet checkpoint processed a deterministic 24-file, eight-speaker sample from public LibriSpeech `dev-clean`: the first three FLAC files under each of the first eight lexicographic speaker directories. The official archive SHA256 was `76f87d090650617fca0cac8f88b9416e0ebf80350acb97b343a85fa903728ab3`.

The 24 same-speaker pair scores ranged from 0.377 to 0.892; the 252 different-speaker pairs ranged from -0.278 to 0.325. At the frozen policy, 23 same-speaker pairs were matches and one was uncertain. No different-speaker pair was a match; six were uncertain and 246 were no-match. Full aggregate evidence is in `titanet-public-calibration-proof.json`.

This is a conservative pilot gate, not a claimed family-video accuracy rate. LibriSpeech is clean read speech and does not represent family video microphones, aging voices, off-camera speech, overlapping speakers or background sound. The four private intervals remain held out until the approved bounded run. Their outcomes may be match, uncertain, or no-match; the thresholds will not be tuned after seeing them.
