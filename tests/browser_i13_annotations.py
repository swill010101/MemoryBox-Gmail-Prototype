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
        functions+=code[code.index("  function bindSpeechTranscript("):code.index("  function appearanceViewBounds(")]
        setup="""(()=>{
 document.body.innerHTML="""+json.dumps(markup)+""";
 document.body.style='margin:0;background:#0b1222;font:16px system-ui';
 const style=document.createElement('style');style.textContent="""+json.dumps(css)+""";document.head.appendChild(style);
 const escapeHtml=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;'),escapeAttr=escapeHtml;
 const immichVideoSrc=()=>'',faceBoxHtml=()=>'',bindTranscribeThisTape=()=>{};
 const state={modal:{openId:'synthetic',transcriptOn:true}};
 const stopSpeechPoll=()=>{},syncTranscribeButton=()=>{},syncLearnSubmitEnabled=()=>{},knownPeopleOptions=()=>[],setSpeechStatus=()=>{};
 const paintTranscriptEmpty=(box,item,message)=>{box.textContent=message;};
 const closeModal=()=>{window.navigated++;},stepViewer=()=>{window.navigated++;};
 window.navigated=0;window.reads=0;window.failSave=false;
 window.historyRows=[];
 window.dataForTest=()=>({annotation_enabled:true,version_id:'00000000-0000-0000-0000-000000000020',provider_key:'hvrt',expected_head:historyRows.at(-1)?.id||null,
 words:Array.from({length:300},(_,i)=>({id:'word-'+i,machine_token:'Original',token:'Original',t_start:i,t_end:i+.5})),history:historyRows});
 window.annotationCalls=[];
 window.fetch=async(url,options)=>{
   if(url==='/people?limit=500')return {ok:true,json:async()=>({people:[{id:'00000000-0000-0000-0000-000000000001',display_name:'Synthetic Person'}]})};
   if(url.startsWith('/speech/transcript?')) {window.reads++;return {ok:true,json:async()=>dataForTest()};}
   window.annotationCalls.push({url,options});
   if(window.failSave)return {ok:false,json:async()=>({detail:'Synthetic save rejected'})};
   const a={...JSON.parse(options.body),id:'annotation-'+annotationCalls.length,t_start:143,t_end:144,created_at:'synthetic',stale:false};
   historyRows.push(a);return {ok:true,json:async()=>({ok:true,annotation:a})};
 };
 if(!crypto.randomUUID)crypto.randomUUID=()=> '00000000-0000-0000-0000-000000000099';
 """+functions+"""
 window.bindSpeechTranscript=bindSpeechTranscript;
 document.addEventListener("keydown",handleViewerKeydown);
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
 const ids=['00000000-0000-0000-0000-000000000011','00000000-0000-0000-0000-000000000012'];
 box.innerHTML='<span class="mb-ev-word" data-i="0">Original</span> <span class="mb-ev-word" data-i="1">words</span><br>'+box.innerHTML;
 window.testItem=item;bindSpeechTranscript(item);
 };
 window.buildProofModal(true);
 return true;
})()"""
        r=await call("Runtime.evaluate",{"expression":setup,"returnByValue":True})
        if "exceptionDetails" in r:raise RuntimeError(r["exceptionDetails"])
        r=await call("Runtime.evaluate",{"expression":"""(async()=>{
 const wait=()=>new Promise(r=>setTimeout(r,80));await wait();
 const box=document.getElementById('mb-ev-transcript');
 const pick=()=>{const els=box.querySelectorAll('.mb-ev-word'),range=document.createRange();range.setStart(els[0].firstChild,0);range.setEnd(els[1].firstChild,8);getSelection().removeAllRanges();getSelection().addRange(range);box.dispatchEvent(new MouseEvent('mouseup',{bubbles:true}));};
 pick();
 let tools=document.querySelector('.mb-transcript-annotations'),button=tools.querySelector('[data-annotation-save]');
 button.click();await wait();const emptyRejected=annotationCalls.length===0;
 const person=tools.querySelector('[data-annotation-person]');person.value='00000000-0000-0000-0000-000000000001';
 person.dispatchEvent(new MouseEvent('mouseup',{bubbles:true}));
 person.dispatchEvent(new KeyboardEvent('keyup',{key:'ArrowDown',bubbles:true}));
 const personRetained=person.value.endsWith('0001');
 const check=tools.querySelector('[data-correct-text]');check.checked=true;check.dispatchEvent(new Event('change'));
 const text=tools.querySelector('textarea');text.focus();text.value='Corrected words';
 for(const el of [text,person,tools.querySelector('[data-annotation-reason]')]) {
 for(const key of ['ArrowLeft','ArrowRight','Escape'])el.dispatchEvent(new KeyboardEvent('keydown',{key,bubbles:true,cancelable:true}));
 }
 const editingDoesNotNavigate=navigated===0;
 button.dispatchEvent(new MouseEvent('mouseup',{bubbles:true}));button.click();await wait();
 tools=document.querySelector('.mb-transcript-annotations');
 const request=annotationCalls[0],payload=request&&JSON.parse(request.options.body);
 const confirmationPersists=tools.querySelector('[data-annotation-status]').textContent.includes('Assignment saved');
 const assignmentRetained=tools.querySelector('[data-annotation-person]').value.endsWith('0001');
 const savedHistory=tools.querySelector('[data-annotation-history]').textContent.includes('assign');
 const openAfterSave=tools.open;
 // Reopen through the actual transcript fetch/render path.
 bindSpeechTranscript(testItem);await wait();tools=document.querySelector('.mb-transcript-annotations');
 const reopenedHistory=tools.querySelector('summary').textContent.includes('1 saved assignment')&&tools.querySelector('[data-annotation-history]').textContent.includes('assign');
 const savedList=tools.querySelector('[data-annotation-history]');
 const visibleAssignmentDetails=tools.querySelector('[data-annotation-list]').open && savedList.textContent.includes('Synthetic Person') && savedList.textContent.includes('2:23.0') && savedList.textContent.includes('Corrected words');
 box.scrollTop=box.scrollHeight;
 const header=tools.querySelector('summary'),hr=header.getBoundingClientRect();
 const headingVisibleAtTranscriptBottom=document.elementFromPoint(hr.left+5,hr.top+5)===header;
 tools.open=true;tools.querySelector('[data-annotation-history] button').click();await wait();
 const reviewRestoresExactWords=box.querySelectorAll('.is-annotation-selected').length===2 && tools.querySelector('[data-annotation-person]').value.endsWith('0001') && tools.querySelector('textarea').value==='Corrected words';
 window.failSave=true;tools.querySelector('[data-annotation-save]').click();await wait();
 const errorVisible=tools.querySelector('[data-annotation-status]').textContent==='Synthetic save rejected';
 const rejectedSaveRetainsPerson=tools.querySelector('[data-annotation-person]').value.endsWith('0001');
 const footer=box.parentElement.getBoundingClientRect();
 const transcriptFits=box.getBoundingClientRect().height>40&&footer.bottom<=innerHeight;
 const save=tools.querySelector('[data-annotation-save]');save.scrollIntoView({block:'nearest'});
 const br=save.getBoundingClientRect();
 const saveReachable=document.elementFromPoint(br.left+3,br.top+3)===save;
 document.body.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));
 return {emptyRejected,personRetained,editingDoesNotNavigate,confirmationPersists,assignmentRetained,savedHistory,openAfterSave,reopenedHistory,visibleAssignmentDetails,reviewRestoresExactWords,headingVisibleAtTranscriptBottom,errorVisible,rejectedSaveRetainsPerson,transcriptFits,saveReachable,
 selectedExactWords:payload?.word_ids.length===2,correction:payload?.correction==='Corrected words',
 annotationOnly:annotationCalls.every(r=>r.url==='/annotations/transcript'),ownerHeader:request?.options.headers['X-MB-Annotation']==='1',viewerNavigationStillWorks:navigated===1};
})()""","awaitPromise":True,"returnByValue":True})
        if "exceptionDetails" in r:raise RuntimeError(r["exceptionDetails"])
        checks=r['result']['value']
        proof={'kind':'actual_annotation_form_and_selection_synthetic_browser','checks':checks,'passed':all(checks.values()),'limits':['Synthetic API responses; persistence tested separately on disposable PostgreSQL','No runtime services or family media']}
        await call('Runtime.evaluate',{'expression':"(async()=>{bindSpeechTranscript(testItem);await new Promise(r=>setTimeout(r,80));document.querySelector('.mb-transcript-annotations').open=true;})()",'awaitPromise':True})
        shot=await call('Page.captureScreenshot' ,{'format':'png'})
        (OUT/'browser-annotation-proof.png').write_bytes(base64.b64decode(shot['data']))
        (OUT/'browser-annotation-proof.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(proof,indent=2))
        await ws.send(json.dumps({'id':seq+1,'method':'Browser.close'}))
        if not proof['passed']:raise RuntimeError('Annotation browser proof failed')

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
            try: proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.terminate();proc.wait(timeout=10)

if __name__=='__main__':main()
