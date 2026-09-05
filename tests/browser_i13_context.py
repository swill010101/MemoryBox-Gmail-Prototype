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
        extracted = code[code.index("  function applyPayloadToState("):code.index("  const ASK_HIST_KEY")]
        extracted += code[code.index("  function peopleList("):code.index("  function syncRailTabs(")]
        extracted += code[code.index("  function setPlaceFilter("):code.index("  function setViewMode(")]
        extracted += code[code.index("  async function liveFind("):code.index("  function currentAskText(")]
        start = code.index("  function applyAskCommand(")
        extracted += code[start:code.index("\n  function ", start + 10)]
        expression = """(async()=>{
 document.body.style='background:#0b1222;color:#edf3ff;font:18px system-ui;padding:32px';
 document.body.innerHTML='<h1>Ask context reset</h1><input id="mb-explore-ask" value="clear all"><pre id="result"></pre>';
 let state={domain:{chips:[{kind:'person',label:'Previous Person'}],typeFilter:'video',undatedFilter:true},gallery:{density:1,sort:'oldest',scrollTop:999}}, rawItems=[],sessionId='old',findGen=0,contextPlaceOverride=null;
 const PERSON_MODE=false;const PERSON=null;
 const clearAskDirty=()=>{},rememberAskLocal=()=>{},hideQuickPreview=()=>{},clearSearchingChrome=()=>{},syncTimelineToEligibleDatedExtent=()=>{};
 const bumpFindGen=()=>++findGen;
 const extentOf=()=>({empty:true}),isDated=()=>false;
 const findErrorMessage=e=>String(e),renderCurator=()=>{};
 const render=()=>{document.getElementById('result').textContent=JSON.stringify(state,null,2)};
 const requests=[];
 const personScopedAsk=q=>q,stopAskStatusPoll=()=>{};
 window.fetch=async(url,opts)=>{requests.push(JSON.parse(opts.body));return {ok:true,json:async()=>({session_id:'fresh',context:{reset:true},items:[],chips:[],summary:'All Ask context cleared.',ask_text:''})}};
 """ + extracted + """
 clearPlaceFilter();
 await liveFind('at Christmas');
 const chipClearSent=Array.isArray(requests[0].context_place_names)&&requests[0].context_place_names.length===0;
 setPlaceFilter('Florida');
 await liveFind('at Christmas');
 const chipSetSent=requests[1].context_place_names.join()==='Florida';
 applyAskCommand('clear all');
 await new Promise(r=>setTimeout(r,25));
 const cleared=state.domain.typeFilter==='all'&&!state.domain.undatedFilter&&state.domain.chips.length===0&&state.modal.openId===null&&sessionId==='fresh'&&rawItems.length===0;
 state.domain.chips=[{kind:'person',label:'Query Person'}];
 const unsupported=peopleList({title:'Query Person',type:'photo',people:[]});
 const supported=peopleList({type:'photo',people:['Evidence Person']});
 const proof={kind:'actual_ask_command_and_gallery_state_component',cleared,chipClearSent,chipSetSent,unsupported,supported,passed:cleared&&chipClearSent&&chipSetSent&&unsupported.length===0&&supported.join()==='Evidence Person',limits:['Synthetic server response; actual browser command and state functions','Live FlightSim retrieval still requires owner review']};
 document.getElementById('result').textContent=JSON.stringify(proof,null,2);
 return proof;
})()"""
        result=await call("Runtime.evaluate",{"expression":expression,"awaitPromise":True,"returnByValue":True})
        if "exceptionDetails" in result:raise RuntimeError(result["exceptionDetails"])
        proof=result["result"]["value"]
        (OUT/"browser-context-proof.json").write_text(json.dumps(proof,indent=2)+"\n",encoding="utf-8")
        shot=await call("Page.captureScreenshot",{"format":"png"})
        (OUT/"browser-context-proof.png").write_bytes(base64.b64decode(shot["data"]))
        print(json.dumps(proof,indent=2))
        if not proof["passed"]:raise RuntimeError("context component proof failed")

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
