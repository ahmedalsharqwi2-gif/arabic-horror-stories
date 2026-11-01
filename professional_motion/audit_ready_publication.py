"""Read-only delivery audit of immutable receipt IDs; never creates posts."""
import json,time
from datetime import datetime,timezone
from pathlib import Path
from film_factory.publish import query

def main():
 grant=json.loads(Path('config/approved_review_publication.json').read_text())
 key='immediate approved-'+grant['profile']+'-'+str(grant['media_run'])
 entry=json.loads(Path('state/publication_stock.json').read_text())['slots'][key]
 folder=Path('professional_motion/delivery');folder.mkdir(parents=True,exist_ok=True)
 for attempt in range(12):
  rows=[]
  for service,receipt in entry['receipts'].items():
   row={'service':service,'id':receipt['id']}
   try:row.update(query('query { post(input: {id: '+json.dumps(receipt['id'])+'}) { id status dueAt sentAt externalLink } }')['post'])
   except Exception as error:row['audit_error']=type(error).__name__
   rows.append(row)
  (folder/'approved-delivery-audit.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
  (folder/'approved-delivery-audit-observation.json').write_text(json.dumps({'checked_at':datetime.now(timezone.utc).isoformat(),'attempt':attempt+1,'all_sent':all(r.get('status')=='sent' for r in rows)},indent=2))
  print(json.dumps(rows,ensure_ascii=False),flush=True)
  if all(r.get('status') not in ('scheduled','sending','pending') for r in rows):break
  if attempt<11:time.sleep(10)
if __name__=='__main__':main()
