"""Offline FR-005 spot-check using the real explore.js binder (synthetic video).

FlightSim manual step: open a family-video appearance in /explore/ui, press play past
the relevance end, confirm playback continues. Record result in acceptance proof JSON.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent


def main() -> int:
    js = (ROOT / "memorybox/explore/static/explore.js").read_text(encoding="utf-8")
    code = js[js.index("  function appearanceViewBounds(") : js.index("  function bindExploreVideoPlayer(")]
    code += """
const handlers={};const el={currentTime:0,pauses:0,addEventListener(k,f){handlers[k]=f;},removeEventListener(k){delete handlers[k];},pause(){this.pauses++;}};
bindAppearanceView(el,{start_sec:12,end_sec:14});const initial=el.currentTime;
handlers.loadedmetadata();el.currentTime=25;
for(const k of ['timeupdate','seeking','seeked','play'])if(handlers[k])handlers[k]();
console.log(JSON.stringify({initial,current:el.currentTime,pauses:el.pauses,passed:initial===12&&el.currentTime===25&&el.pauses===0}));
"""
    result = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True)
    proof = json.loads(result.stdout.strip())
    proof["kind"] = "fr005_binder_spotcheck_offline"
    proof["flightsim_manual"] = (
        "On /explore/ui open a video moment; verify playback continues past relevance end."
    )
    out = OUT / "fr005-playback-spotcheck-proof.json"
    out.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": proof.get("passed"), "output": str(out), "proof": proof}, indent=2))
    return 0 if proof.get("passed") else 2


if __name__ == "__main__":
    raise SystemExit(main())
