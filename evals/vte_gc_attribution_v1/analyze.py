import json
from pathlib import Path
import sys
root=Path(__file__).parent
for case in sys.argv[1:]:
 p=root/case;m=json.loads((p/'measure-timeline.json').read_text());a=json.loads((p/'app-timeline.json').read_text());r=json.loads((p/'receipt.json').read_text())
 summaries=[]
 for t in r['cancel']:
  v='probe'+str(t['index']);start=next(x['ns'] for x in m if x['name']=='trial-start' and x['input']==v)
  stop=start+int((t['elapsed_ms']+20)*1e6)
  mt=[x for x in m if start<=x['ns']<stop]
  at=[x for x in a if x['phase']==v and start<=x['ns']<stop]
  def since(items,name,match=lambda x:True):
   return next((round((x['ns']-start)/1e6,3) for x in items if x['name']==name and match(x)),None)
  item={'trial':v,'command_start':since(mt,'input-command-start'),'command_end':since(mt,'input-command-end'),'escape_bytes':since(at,'parser-bytes',lambda x:x['value']==repr('\x1b')),'driver_escape':since(at,'driver-key',lambda x:x['key']=='escape'),'handler_start':since(at,'cancel-handler-enter'),'handler_end':since(at,'cancel-handler-exit'),'worker_cancel':since(at,'worker-cancelling'),'terminal_write':since(at,'driver-write',lambda x:x['cancelling']),'after_refresh':since(at,'cancel-after-refresh'),'vte_text':since(mt,'cancel-text-observed'),'vte_pixels':since(mt,'cancel-pixels-observed')}
  layouts=[x for x in at if x['name']=='_refresh_layout']
  item['layout_ms']=round(sum(x['duration_ms'] for x in layouts),3)
  item['layouts']=[{'start_ms':round((x['start_ns']-start)/1e6,3),'duration_ms':round(x['duration_ms'],3)} for x in layouts]
  summaries.append(item)
 (p/'timeline-summary.json').write_text(json.dumps(summaries,indent=2)+'\n')
 print(case, json.dumps(summaries,indent=2))
