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
        binder=code[code.index("  function appearanceViewBounds("):code.index("  function bindExploreVideoPlayer(")]
        expression="""(async()=>{
 document.body.style='background:#0b1222;color:#edf3ff;font:18px system-ui;padding:32px';
 document.body.innerHTML='<h1>I13 source playback proof</h1><p>Synthetic canvas source. No archive media or models.</p><canvas width="640" height="240"></canvas><br><video muted controls width="640"></video><pre id="result">Recording synthetic source in memory...</pre>';
 const canvas=document.querySelector('canvas'),ctx=canvas.getContext('2d');canvas.style.display='none';
 const stream=canvas.captureStream(15),chunks=[];
 const rec=new MediaRecorder(stream,{mimeType:'video/webm;codecs=vp8'});
 rec.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};
 const stopped=new Promise(resolve=>rec.onstop=resolve);
 let frame=0;const draw=setInterval(()=>{ctx.fillStyle='#24395e';ctx.fillRect(0,0,640,240);ctx.fillStyle='white';ctx.font='30px sans-serif';ctx.fillText('Synthetic source frame '+frame++,35,110);},65);
 rec.start();await new Promise(r=>setTimeout(r,4200));rec.stop();await stopped;clearInterval(draw);stream.getTracks().forEach(t=>t.stop());
 const video=document.querySelector('video');
 const blob=new Blob(chunks,{type:'video/webm'});video.src=URL.createObjectURL(blob);
 """+binder+"""
 bindAppearanceView(video,{start_sec:0.5,end_sec:1});
 await new Promise(resolve=>video.addEventListener('loadedmetadata',resolve,{once:true}));
 const seek=video.currentTime;
 await video.play();await new Promise(r=>setTimeout(r,2000));
 const proof={kind:'rendered_chromium_synthetic_source',initial_seek:seek,relevance_end:1,observed_time:video.currentTime,paused:video.paused,passed:seek===0.5&&video.currentTime>1.5&&!video.paused,limits:['Synthetic source only','Full Gallery/provider workflow not exercised']};
 document.getElementById('result').textContent=JSON.stringify(proof,null,2);
 video.pause();return proof;
})()"""
        result=await call("Runtime.evaluate",{"expression":expression,"awaitPromise":True,"returnByValue":True})
        if "exceptionDetails" in result:raise RuntimeError(result["exceptionDetails"])
        proof=result["result"]["value"]
        (OUT/"browser-playback-proof.json").write_text(json.dumps(proof,indent=2)+"\n",encoding="utf-8")
        shot=await call("Page.captureScreenshot",{"format":"png"})
        (OUT/"browser-playback-proof.png").write_bytes(base64.b64decode(shot["data"]))
        print(json.dumps(proof,indent=2))
        if not proof["passed"]:raise RuntimeError("continuous playback proof failed")

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
