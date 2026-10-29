"""Read-only provider status; never submits a post."""
import json
from pathlib import Path
from film_factory.publish import query

def main():
 grant=json.loads(Path('config/approved_review_publication.json').read_text())
 key='immediate approved-'+grant['profile']+'-'+str(grant['media_run'])
 result=json.loads(Path('state/publication_stock.json').read_text())['slots'][key];rows=[]
 for service,receipt in result['receipts'].items():
  if not receipt:continue
  row={'service':service,'id':receipt['id']}
  try:row.update(query('query { post(input: {id: '+json.dumps(receipt['id'])+'}) { id status dueAt sentAt externalLink } }')['post'])
  except Exception as error:row['audit_error']=type(error).__name__
  rows.append(row)
 Path('professional_motion/delivery').mkdir(parents=True,exist_ok=True)
 Path('professional_motion/delivery/approved-delivery-audit.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2));print(json.dumps(rows,ensure_ascii=False))
if __name__=='__main__':main()
