"""Product-only publisher. Persist the lock to GitHub BEFORE Meta side effects."""
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import json
import os
import subprocess
from instagram_factory.api import InstagramAPI
from instagram_factory.config import Settings
from instagram_factory.pipeline import Pipeline

QUEUE = Path('product_queue.json')
BLOCKED = {'publishing', 'publishing_unknown', 'publish_paused', 'error'}

def persist(posts):
    tmp = QUEUE.with_suffix('.tmp')
    tmp.write_text(json.dumps(posts, ensure_ascii=False, indent=2)+'\n')
    tmp.replace(QUEUE)
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise RuntimeError('Publishing requires durable GitHub state')
    subprocess.run(['git','add',str(QUEUE)],check=True)
    subprocess.run(['git','commit','-m','chore: persist product publishing state'],check=True)
    subprocess.run(['git','push','origin','HEAD:main'],check=True)

def select_due(posts, now):
    if any(p.get('status') in BLOCKED for p in posts):
        return None
    due = [p for p in posts if p.get('status')=='ready' and p.get('production_approved') is True and datetime.fromisoformat(p['scheduled_at'])<=now]
    return min(due,key=lambda p:p['scheduled_at']) if due else None

def validate(post):
    if not post['id'].startswith('buyerfire-products-') or post.get('media_type')!='reel':
        raise ValueError('Not a product reel')
    if post.get('caption')!='мой бутик в шапке профиля:':
        raise ValueError('Unexpected caption')
    if not all(post.get('qa',{}).get(k) is True for k in ('visual','readability','products','audio_rights','technical')):
        raise ValueError('QA incomplete')
    path=Path(post['video_asset'])
    if path.is_absolute() or '..' in path.parts or not path.is_file():
        raise ValueError('Invalid asset')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=post['sha256']:
        raise ValueError('Asset changed since QA')

def run():
    s=Settings(queue_path=QUEUE, insights_path=Path('product_insights.json'))
    s.require_publish()
    api=InstagramAPI(s.access_token,s.user_id,s.api_version,s.api_host)
    posts=json.loads(QUEUE.read_text())
    now=datetime.now(s.timezone)
    p=select_due(posts,now)
    if any(x.get('status') in BLOCKED for x in posts):
        raise RuntimeError('Publishing paused; reconcile Meta result first')
    if not p:
        print(json.dumps({'published':0,'reason':'nothing_approved_due','ready':sum(x.get('status')=='ready' for x in posts)}))
    else:
        try:
            validate(p)
            if now-datetime.fromisoformat(p['scheduled_at'])>timedelta(hours=2):
                p['status']='missed_slot'; persist(posts); return
            published=[x for x in posts if x.get('status')=='published' and x.get('published_at')]
            today=[x for x in published if datetime.fromisoformat(x['published_at']).astimezone(s.timezone).date()==now.date()]
            if len(today)>=3 or any(now-datetime.fromisoformat(x['published_at'])<timedelta(hours=3) for x in published):
                print('{"published":0,"reason":"daily_or_spacing_guard"}'); return
            account=api._request('GET',s.user_id,{'fields':'id,username'})
            if account.get('username','').lower()!='geobuyerfire':
                raise ValueError('Target account mismatch')
            limit=api.content_publishing_limit()
            row=(limit.get('data') or [{}])[0]
            usage=row.get('quota_usage'); total=(row.get('config') or {}).get('quota_total')
            if not isinstance(usage,int) or not isinstance(total,int) or total<=0 or usage>=total:
                raise ValueError('Quota not verified or reached')
            p['last_quota']={'usage':usage,'total':total,'checked_at':now.isoformat()}
            p['status']='publishing'; persist(posts)
            p['container_id']=api.create_reel_container(s.asset_base_url+'/'+p['video_asset'],p['caption'],True)
            persist(posts)
            api.wait_until_ready(p['container_id'],attempts=60,delay=5)
            p['status']='publishing_unknown'; persist(posts)
            p['published_media_id']=api.publish_container(p['container_id'])
            p['published_at']=datetime.now(s.timezone).isoformat()
            p['status']='published'; persist(posts)
            print(json.dumps({'published':1,'post_id':p['id'],'media_id':p['published_media_id']}))
        except Exception as exc:
            # No raw API error body or credential-bearing URL in public logs.
            if p.get('status')!='published':
                p['status']='publish_paused'; p['error_type']=type(exc).__name__
                persist(posts)
            raise RuntimeError('Product publisher stopped; check persisted state') from None
    print(json.dumps(Pipeline(s).collect_insights()))

if __name__=='__main__':
    run()
