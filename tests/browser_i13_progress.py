"""Offline Chromium proof of actual Ask reset and evidence-label components.
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
        extracted = code[code.index("  let askStatusTimer = null;"):code.index("  function showSearching(")]
        extracted += code[code.index("  async function liveFind("):code.index("  function currentAskText(")]
        expression = """(async()=>{
 document.body.style='background:#0b1222;color:#edf3ff;font:18px system-ui;padding:32px';
 document.body.innerHTML='<h1>Curator progress</h1><div id="mb-explore-curator-body"></div><pre id="result"></pre>';
 let state={domain:{}},sessionId='old-session',contextPlaceOverride=null;
 const personScopedAsk=q=>q;
 let tick,reply={line:'Done'},releaseOld;
 const requests=[];
 window.setInterval=fn=>{tick=fn;return 1};window.clearInterval=()=>{};
 window.fetch=async(url,opts)=>{
   if(opts.body){requests.push(JSON.parse(opts.body));return {ok:true,json:async()=>({})}}
   if(reply==='deferred')return new Promise(resolve=>{releaseOld=resolve});
   return {json:async()=>reply};
 };
 """+extracted+"""
 const flush=()=>new Promise(r=>setTimeout(r,0));
 setCuratorStatusLine('Collecting photos');
 startAskStatusPoll();const firstId=askProgressId;
 tick();await flush();
 const oldDoneIgnored=state.domain.summary==='Collecting photos';
 reply={line:'Collecting videos'};tick();await flush();
 const currentShown=state.domain.summary==='Collecting videos';
 reply='deferred';tick();await flush();
 startAskStatusPoll();const secondId=askProgressId;
 setCuratorStatusLine('Collecting photos');
 releaseOld({json:async()=>({line:'Old request status'})});await flush();
 const lateIgnored=state.domain.summary==='Collecting photos';
 await liveFind('show me Example Person');
 const idSent=requests[0].progress_id===secondId;
 const proof={oldDoneIgnored,currentShown,lateIgnored,idSent,distinctIds:firstId!==secondId,passed:oldDoneIgnored&&currentShown&&lateIgnored&&idSent&&firstId!==secondId,limits:['Actual progress DOM and request functions with synthetic responses','Live curator acceptance remains pending']};
 document.getElementById('result').textContent=JSON.stringify(proof,null,2);
 return proof;
})()"""
        result=await call("Runtime.evaluate",{"expression":expression,"awaitPromise":True,"returnByValue":True})
        if "exceptionDetails" in result:raise RuntimeError(result["exceptionDetails"])
        proof=result["result"]["value"]
        (OUT/"browser-progress-proof.json").write_text(json.dumps(proof,indent=2)+"\n",encoding="utf-8")
        shot=await call("Page.captureScreenshot",{"format":"png"})
        (OUT/"browser-progress-proof.png").write_bytes(base64.b64decode(shot["data"]))
        print(json.dumps(proof,indent=2))
        if not proof["passed"]:raise RuntimeError("progress component proof failed")

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
