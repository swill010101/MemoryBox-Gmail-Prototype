"""Offline Chromium proof using a synthetic canvas video recorded in browser memory.
No application server, source media, recognition, transcription or runtime DB is used.
"""
import asyncio
import base64
import json
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request
import websockets

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"docs/implementation/p2-i13-stage-a"

async def run(endpoint):
    async with websockets.connect(endpoint, max_size=8*1024*1024) as ws:
        seq=0
        async def call(method,params=None):
            nonlocal seq
            seq+=1;identifier=seq
            await ws.send(json.dumps({"id":identifier,"method":method,"params":params or {}}))
            while True:
                answer=json.loads(await ws.recv())
                if answer.get("id")==identifier:
                    if "error" in answer:raise RuntimeError(answer["error"])
                    return answer.get("result",{})
        await call("Page.enable")
        await call("Emulation.setDeviceMetricsOverride", {"width":1000,"height":850,"deviceScaleFactor":1,"mobile":False})
        await call("Page.navigate",{"url":"about:blank"})
        code=(ROOT/"memorybox/explore/static/explore.js").read_text(encoding="utf-8")
        css=(ROOT/"memorybox/explore/static/explore.css").read_text(encoding="utf-8")
        html=(ROOT/"memorybox/explore/static/explore.html").read_text(encoding="utf-8")
        markup=html[html.index('  <div class="mb-modal-backdrop"'):html.index('  <div class="mb-comms-filter"')]
        functions=code[code.index("  function renderEvidenceBody("):code.index("  function quickPreviewHtml(")]
        functions+=code[code.index("  function renderViewerFooter("):code.index("  function renderTeachSlot(")]
        functions+=code[code.index("  function bindSourceMoments("):code.index("  function bindExploreVideoPlayer(")]
        if "  function setViewerMediaType(" in code:
            functions+=code[code.index("  function setViewerMediaType("):code.index("  function renderViewer(")]
        else:
            functions+="function setViewerMediaType(item) {}"
        setup="""(()=>{
 document.body.innerHTML="""+json.dumps(markup)+""";
 document.body.style='margin:0;background:#0b1222;font:16px system-ui';
 const style=document.createElement('style');style.textContent="""+json.dumps(css)+""";document.head.appendChild(style);
 const escapeHtml=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;'),escapeAttr=escapeHtml;
 const immichVideoSrc=()=>'',faceBoxHtml=()=>'',bindTranscribeThisTape=()=>{};
 """+functions+"""
 window.buildProofModal=(withMoments)=>{
 const item={id:'synthetic',type:'video',video_external_id:'synthetic',start_sec:.5,end_sec:1,t:.5};
 if(withMoments)item.source_moments=[{start_sec:.5},{start_sec:10.5}];
 setViewerMediaType(item);
 document.getElementById('mb-modal').hidden=false;
 document.getElementById('mb-modal-title').textContent='Synthetic source video';
 document.getElementById('mb-modal-kicker').textContent='VIDEO';
 document.getElementById('mb-modal-body').innerHTML=renderEvidenceBody(item);
 renderViewerFooter(item);bindSourceMoments(item);
 const video=document.querySelector('video');video.width=1280;video.height=720;
 video.poster='data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720"><rect width="1280" height="720" fill="#24395e"/><text x="120" y="360" fill="white" font-size="48">Synthetic video - layout check</text></svg>');
 document.getElementById('mb-rail-panel').textContent='People and source details remain in the existing side panel.';
 const box=document.getElementById('mb-ev-transcript');
 box.innerHTML=Array.from({length:120},(_,i)=>'<span>Transcript line '+(i+1)+': sample speech remains readable and selectable.</span><br>').join('')+'<button id="transcript-end">Last transcript line</button>';
 };
 window.buildProofModal(true);
 return true;
})()"""
        r=await call("Runtime.evaluate",{"expression":setup,"returnByValue":True})
        if "exceptionDetails" in r:raise RuntimeError(r["exceptionDetails"])
        cases=[]
        for width,height in [(1208,832),(1024,640),(800,600),(640,480)]:
            await call("Emulation.setDeviceMetricsOverride",{"width":width,"height":height,"deviceScaleFactor":1,"mobile":False})
            for moments in [True,False]:
                expression="""(async()=>{
 buildProofModal("""+json.dumps(moments)+""");await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
 const modal=document.querySelector('.mb-viewer'),box=document.getElementById('mb-ev-transcript'),video=document.querySelector('video');
 const m=modal.getBoundingClientRect(),t=box.getBoundingClientRect(),v=video.getBoundingClientRect();
 box.scrollTop=box.scrollHeight;const end=document.getElementById('transcript-end');end.focus({preventScroll:true});const e=end.getBoundingClientRect();
 const select=document.querySelector('.mb-source-moments select'),j=select&&select.getBoundingClientRect();
 const footerVisible=t.top>=m.top&&t.bottom<=m.bottom+1&&t.height>=70;
 const lastReachable=e.top>=t.top&&e.bottom<=t.bottom+1&&document.elementFromPoint(e.left+5,e.top+5)===end;
 const jumpVisible=!j||(j.top>=m.top&&j.bottom<=t.top);
 const playerVisible=v.top>=m.top&&v.bottom<=t.top+1&&v.height>=65;
 const descriptionRemoved=!document.querySelector('.mb-source-moments p');
 return {width:innerWidth,height:innerHeight,moments:!!select,transcriptHeight:t.height,playerHeight:v.height,footerVisible,lastReachable,jumpVisible,playerVisible,descriptionRemoved,modalFits:m.top>=0&&m.bottom<=innerHeight+1,passed:footerVisible&&lastReachable&&jumpVisible&&playerVisible&&descriptionRemoved&&m.bottom<=innerHeight+1};
})()"""
                r=await call("Runtime.evaluate",{"expression":expression,"awaitPromise":True,"returnByValue":True})
                if "exceptionDetails" in r:raise RuntimeError(r["exceptionDetails"])
                cases.append(r["result"]["value"])
        await call("Emulation.setDeviceMetricsOverride",{"width":1208,"height":832,"deviceScaleFactor":1,"mobile":False})
        await call("Runtime.evaluate",{"expression":"buildProofModal(true)"})
        await asyncio.sleep(.1)
        shot=await call("Page.captureScreenshot",{"format":"png"})
        (OUT/"browser-modal-fit-proof.png").write_bytes(base64.b64decode(shot["data"]))
        proof={"kind":"actual_modal_markup_css_and_video_transcript_renderers","cases":cases,"passed":all(c["passed"] for c in cases),"limits":["Synthetic video poster and transcript, no runtime services/media","Playback/navigation exercised by existing component tests"]}
        (OUT/"browser-modal-fit-proof.json").write_text(json.dumps(proof,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(proof,indent=2))
        if not proof["passed"]:raise RuntimeError("Modal transcript fit failed")

def main():
    browser=Path('C:/Program Files/Google/Chrome/Application/chrome.exe')
    with tempfile.TemporaryDirectory(prefix='i13-browser-',dir=OUT) as tmp:
        profile=Path(tmp).resolve()
        assert profile.is_relative_to(OUT.resolve())
        proc=subprocess.Popen([str(browser),'--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--autoplay-policy=no-user-gesture-required','--remote-debugging-port=0','--user-data-dir='+str(profile),'about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            portfile=profile/'DevToolsActivePort'
            for _ in range(100):
                if portfile.exists():break
                time.sleep(.1)
            port=portfile.read_text().splitlines()[0]
            with urllib.request.urlopen('http://127.0.0.1:'+port+'/json/list') as r:tabs=json.load(r)
            endpoint=next(t['webSocketDebuggerUrl'] for t in tabs if t['type']=='page')
            asyncio.run(run(endpoint))
        finally:
            proc.terminate();proc.wait(timeout=10)

if __name__=='__main__':main()
