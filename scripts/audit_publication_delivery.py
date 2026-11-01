"""Read provider states without exposing credentials or treating acceptance as delivery."""
import json,re
from pathlib import Path
from film_factory.publish import query

def main():
 p=Path('state/publication_stock.json')
 stock=json.loads(p.read_text()) if p.exists() else {'slots':{}}
 rows=[]
 for slot,entry in stock.get('slots',{}).items():
  for service,receipt in entry.get('receipts',{}).items():
   ident=receipt.get('id','');row={'slot':slot,'service':service,'id':ident}
   if re.fullmatch(r'[a-f0-9]{24}',ident):
    try:row.update(query('query { post(input: {id: '+json.dumps(ident)+'}) { id status dueAt sentAt externalLink channelService allowedActions } }')['post'])
    except Exception as exc:row['audit_error']=type(exc).__name__
   elif service=='youtube':row.update(externalLink='https://www.youtube.com/watch?v='+ident,status='accepted_direct_upload')
   rows.append(row)
 Path('output').mkdir(exist_ok=True)
 Path('output/social-delivery-audit.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
 print(json.dumps(rows,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
