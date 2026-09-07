"""Read-only playback preflight for patio video 003; no media or database writes."""
from __future__ import annotations
import hashlib,json,os,shutil,subprocess
from pathlib import Path
VID='vid-8163a680131fd30a'; SHA='ccda7f166a780c512fa9dc72b366ad20b314003aa6cc2f3869a0cf5396dc37e1'; SIZE=1055204616
SOURCE=Path(r'P:\Photos\Home Videos\2011-03-13 Grandpa sessions\Grandpa sessions 003.MP4')
ROOT=Path(r'C:\Users\tomwi\AppData\Local\Temp\memorybox_video_derived')
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def proxy_path(root,vid): return root/'browser_proxies'/(hashlib.sha256(vid.encode()).hexdigest()[:24]+'.mp4')
def main():
 if os.environ.get('MEMORYBOX_RECOGNITION_DRAIN')!='0' or os.environ.get('MEMORYBOX_SPEECH_DRAIN')!='0' or os.environ.get('MEMORYBOX_I13_ADMISSION_ID'): raise RuntimeError('Drains must be 0 and admission unset')
 if not SOURCE.is_file(): raise RuntimeError('Original is unavailable')
 if SOURCE.stat().st_size!=SIZE or digest(SOURCE)!=SHA: raise RuntimeError('Original does not match the 22-source manifest')
 root=ROOT.resolve(strict=True); dest=proxy_path(root,VID)
 ffprobe=shutil.which('ffprobe');
 if not ffprobe: raise RuntimeError('ffprobe missing')
 out=subprocess.run([ffprobe,'-v','error','-show_streams','-show_format','-of','json',str(SOURCE)],capture_output=True,text=True,timeout=60,check=True).stdout
 data=json.loads(out); streams=data.get('streams',[]);v=[x for x in streams if x.get('codec_type')=='video'];a=[x for x in streams if x.get('codec_type')=='audio']
 print(json.dumps({'ok':True,'mode':'check_only','source_id':VID,'source':str(SOURCE),'original':{'bytes':SIZE,'sha256':SHA},'streams':{'video_streams':len(v),'audio_streams':len(a),'video_codec':v[0].get('codec_name') if v else None,'pixel_format':v[0].get('pix_fmt') if v else None,'duration_sec':float(data.get('format',{}).get('duration','nan')),'audio_codecs':[x.get('codec_name') for x in a]},'destination':str(dest),'destination_exists':dest.exists(),'private_media_processed':False,'database_writes':False,'next':'Stop. Review this report before any separate one-source staging proposal.'},indent=2))
if __name__=='__main__':
 try: main()
 except Exception as e: print(json.dumps({'ok':False,'error_type':type(e).__name__,'message':str(e),'action':'Stop; no proxy was created.'}));raise SystemExit(2)
