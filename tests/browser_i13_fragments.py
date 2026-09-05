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
        binder=code[code.index("  function appearanceViewBounds("):code.index("  function bindSourceMoments(")]
        navigation=code[code.index("  function bindSourceMoments("):code.index("  function bindExploreVideoPlayer(")]
        card=code[code.index("  function cardMediaInner("):code.index("  function bindLazyThumbs(")]
        css=(ROOT/"memorybox/explore/static/explore.css").read_text(encoding="utf-8")
        expression="""(async()=>{
 const style=document.createElement('style');style.textContent="""+json.dumps(css)+""";document.head.appendChild(style);
 document.body.style='background:#0b1222;color:#edf3ff;font:16px system-ui;padding:24px';
 document.body.innerHTML='<h1>Source video - evidence moments</h1><p>Synthetic browser verification; no family media or services.</p><div id="card" style="position:relative;width:240px;height:70px;border:1px solid #344155;margin-bottom:12px"></div><div style="max-width:800px;border:1px solid #344155;border-radius:12px;padding:20px"><div><video class="mb-ev-video-player" muted controls width="720"></video></div></div><canvas width="720" height="300" style="display:none"></canvas><pre id="result"></pre>';
 const escapeHtml=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;'),escapeAttr=escapeHtml;
 const canvas=document.querySelector('canvas'),ctx=canvas.getContext('2d'),stream=canvas.captureStream(15),chunks=[];
 const rec=new MediaRecorder(stream,{mimeType:'video/webm;codecs=vp8'});rec.ondataavailable=e=>{if(e.data.size)chunks.push(e.data)};
 const stopped=new Promise(r=>rec.onstop=r);let n=0;
 const draw=setInterval(()=>{ctx.fillStyle='#24395e';ctx.fillRect(0,0,720,300);ctx.fillStyle='white';ctx.font='28px sans-serif';ctx.fillText('Synthetic source frame '+n++,40,130)},65);
 rec.start();await new Promise(r=>setTimeout(r,4200));rec.stop();await stopped;clearInterval(draw);stream.getTracks().forEach(t=>t.stop());
 const video=document.querySelector('video');
 const item={id:'video:source:synthetic',type:'video',video_external_id:'synthetic',start_sec:.5,end_sec:1,t:.5,preview:'2 moments in this result',source_moments:[{id:'a',start_sec:.5,end_sec:1},{id:'b',start_sec:1.5,end_sec:2}]};
 const saved=JSON.stringify(item);
 """+binder+navigation+card+"""
 document.getElementById('card').innerHTML=cardMediaInner(item);
 bindAppearanceView(video,item);bindSourceMoments(item);
 const select=document.querySelector('.mb-source-moments select');
 const disabledBefore=select.disabled;
 video.src=URL.createObjectURL(new Blob(chunks,{type:'video/webm'}));
 await new Promise(r=>video.addEventListener('loadedmetadata',r,{once:true}));
 await new Promise(r=>setTimeout(r,100));
 const firstSeek=video.currentTime;
 select.value='1';select.dispatchEvent(new Event('change'));
 await new Promise(r=>setTimeout(r,100));
 const chosenSeek=video.currentTime,pausedAfterSeek=video.paused,sourceUrl=video.currentSrc;
 await video.play();await new Promise(r=>setTimeout(r,1000));
 const pastEnd=video.currentTime>2.2&&!video.paused;
 video.pause();
 const proof={kind:'actual_source_card_and_moment_navigation_synthetic_browser',disabledBefore,enabledAfter:!select.disabled,firstSeek,chosenSeek,pausedAfterSeek,pastEnd,sourceUnchanged:video.currentSrc===sourceUrl,itemUnchanged:JSON.stringify(item)===saved,options:select.options.length,cardBadge:document.querySelector('#card .mb-card-dur').textContent,limits:['Synthetic browser component, not FlightSim media','Gallery snapshot navigation covered separately; owner workflow acceptance pending']};
 proof.passed=disabledBefore&&proof.enabledAfter&&firstSeek===.5&&chosenSeek===1.5&&pausedAfterSeek&&pastEnd&&proof.sourceUnchanged&&proof.itemUnchanged&&proof.options===2&&proof.cardBadge==='2 moments';
 document.getElementById('result').textContent=JSON.stringify(proof,null,2);return proof;
})()"""
        result=await call("Runtime.evaluate",{"expression":expression,"awaitPromise":True,"returnByValue":True})
        if "exceptionDetails" in result:raise RuntimeError(result["exceptionDetails"])
        proof=result["result"]["value"]
        (OUT/"browser-fragment-proof.json").write_text(json.dumps(proof,indent=2)+"\n",encoding="utf-8")
        shot=await call("Page.captureScreenshot",{"format":"png"})
        (OUT/"browser-fragment-proof.png").write_bytes(base64.b64decode(shot["data"]))
        print(json.dumps(proof,indent=2))
        if not proof["passed"]:raise RuntimeError("source moment navigation proof failed")

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
