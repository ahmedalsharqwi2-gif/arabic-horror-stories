import io,json,os,re,subprocess,zipfile
from pathlib import Path
import requests
run=os.environ['INSPECT_RUN_ID'];repo=os.environ['GITHUB_REPOSITORY']
r=requests.get(f'https://api.github.com/repos/{repo}/actions/runs/{run}/logs',headers={'Authorization':'Bearer '+os.environ['GITHUB_TOKEN'],'Accept':'application/vnd.github+json'},timeout=90);r.raise_for_status()
rows=[]
with zipfile.ZipFile(io.BytesIO(r.content)) as z:
 for name in z.namelist():
  if 'Choose a genuinely new sourced topic' not in name:continue
  text=z.read(name).decode('utf8','replace')
  for line in text.splitlines():
   if re.search(r'RuntimeError:|ValueError:|HTTPError:|Traceback|File "/|Skipped|No unused',line) and not re.search(r'KEY|TOKEN|SECRET|Authorization|password|CLIENT_ID',line,re.I):rows.append(line[:800])
out=Path('professional_motion/delivery');out.mkdir(exist_ok=True)
(out/'planning-diagnostic.json').write_text(json.dumps({'prior_run':run,'planning_error_lines':rows[-25:]},indent=2))
def git(*a,data=None):return subprocess.check_output(['git',*a],input=data).decode().strip()
blob=git('hash-object','-w',str(out/'planning-diagnostic.json'));tree=git('mktree',data=f'100644 blob {blob}\tplanning-diagnostic.json\n'.encode());commit=git('-c','user.name=review-bot','-c','user.email=bot@users.noreply.github.com','commit-tree',tree,'-m','Safe planning diagnostics [skip ci]')
git('push','origin',commit+':refs/heads/codex/planning-diagnostic-'+run)
