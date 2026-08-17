import json,re,urllib.request,urllib.parse,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
DATA=ROOT/'site-data.json'
HEAD={'User-Agent':'Mozilla/5.0 MainRoomLiverpool/1.0'}
def getjson(url):
    req=urllib.request.Request(url,headers=HEAD);return json.loads(urllib.request.urlopen(req,timeout=25).read())
def gettext(url):
    req=urllib.request.Request(url,headers=HEAD);return urllib.request.urlopen(req,timeout=25).read()
def load(): return json.loads(DATA.read_text())
def espn_fixtures(slug):
    j=getjson(f'https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/teams/364/schedule?season=2026')
    out=[]
    for ev in j.get('events',[]):
      comp=(ev.get('competitions') or [{}])[0];cs=comp.get('competitors',[]);lfc=next((c for c in cs if str(c.get('team',{}).get('id'))=='364'),None);opp=next((c for c in cs if c is not lfc),None)
      if not lfc or not opp: continue
      status=(comp.get('status') or {}).get('type',{});done=status.get('completed',False)
      b=[]
      for br in comp.get('broadcasts',[]) or []: b += br.get('names',[]) or []
      out.append({'id':str(ev.get('id')),'date':ev.get('date'),'opponent':opp.get('team',{}).get('displayName'),'homeAway':'H' if lfc.get('homeAway')=='home' else 'A','competition':'Champions League' if slug=='uefa.champions' else 'Premier League','venue':(comp.get('venue') or {}).get('fullName',''),'broadcastUS':', '.join(dict.fromkeys(b)) if b else ('Paramount+' if slug=='uefa.champions' else 'TBA'),'status':'final' if done else 'scheduled','scoreFor':lfc.get('score',{}).get('displayValue') if isinstance(lfc.get('score'),dict) else lfc.get('score'),'scoreAgainst':opp.get('score',{}).get('displayValue') if isinstance(opp.get('score'),dict) else opp.get('score')})
    return out
def standings(slug):
    j=getjson(f'https://site.api.espn.com/apis/v2/sports/soccer/{slug}/standings?season=2026')
    groups=j.get('children') or [j];entries=[]
    for g in groups:
      st=(g.get('standings') or {}).get('entries',[])
      if len(st)>len(entries): entries=st
    out=[]
    for e in entries:
      team=e.get('team',{});stats={s.get('name'):s.get('value') for s in e.get('stats',[])}
      out.append({'pos':int(stats.get('rank') or len(out)+1),'team':team.get('displayName'),'p':int(stats.get('gamesPlayed') or 0),'w':int(stats.get('wins') or 0),'d':int(stats.get('ties') or 0),'l':int(stats.get('losses') or 0),'gd':int(stats.get('pointDifferential') or stats.get('goalDifference') or 0),'pts':int(stats.get('points') or 0)})
    return sorted(out,key=lambda x:x['pos'])
def news():
  sources=[('The Anfield Wrap','theanfieldwrap.com'),('The Athletic','nytimes.com/athletic'),('BBC','bbc.com/sport'),('Liverpool FC','liverpoolfc.com/news'),('The Guardian','theguardian.com/football'),('Reuters','reuters.com/sports/soccer'),('Liverpool Offside','liverpooloffside.sbnation.com')]
  items=[]
  for label,site in sources:
    try:
      q=urllib.parse.quote(f'Liverpool FC site:{site}');url=f'https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en';root=ET.fromstring(gettext(url))
      for it in root.findall('.//item')[:3]:
        title=(it.findtext('title') or '').strip();link=(it.findtext('link') or '').strip();pub=(it.findtext('pubDate') or '').strip()
        if 'sun' in title.lower() and 'sunderland' not in title.lower(): continue
        try: dt=datetime.strptime(pub,'%a, %d %b %Y %H:%M:%S %Z').replace(tzinfo=timezone.utc).isoformat().replace('+00:00','Z')
        except: dt=''
        items.append({'title':re.sub(r'\s+-\s+[^-]+$','',title),'source':label,'url':link,'published':dt})
    except Exception as e: print('news',label,e)
  items.sort(key=lambda x:x.get('published',''),reverse=True);return items[:18]
def merge_broadcasts(new,old):
  manual={(x['date'][:10],x['opponent']):x.get('broadcastUS') for x in old if x.get('broadcastUS') not in (None,'','TBA')}
  for x in new:
    key=(x['date'][:10],x['opponent'])
    if key in manual and x.get('broadcastUS') in ('',None,'TBA'): x['broadcastUS']=manual[key]
  for x in new:
    if x['opponent']=='Newcastle United' and x['date'].startswith('2026-08-23'): x['broadcastUS']='USA Network'
  return new
def main():
  d=load();old=d.get('fixtures',[]);fixtures=[]
  try: fixtures+=merge_broadcasts(espn_fixtures('eng.1'),old)
  except Exception as e: print('PL fixtures',e);fixtures += [x for x in old if x.get('competition')=='Premier League']
  try: fixtures+=espn_fixtures('uefa.champions')
  except Exception as e: print('UCL fixtures',e);fixtures += [x for x in old if x.get('competition')=='Champions League']
  if fixtures:d['fixtures']=sorted(fixtures,key=lambda x:x['date'])
  try:d['premierLeagueTable']=standings('eng.1') or d.get('premierLeagueTable',[])
  except Exception as e:print('PL table',e)
  try:
    u=standings('uefa.champions');d['championsLeagueTable']=u
    if u:d['championsLeagueStatus']='Liverpool’s Champions League league-phase table. Updated automatically.'
  except Exception as e:print('UCL table',e)
  n=news()
  if n:d['news']=n
  d['updated']=datetime.now(timezone.utc).isoformat().replace('+00:00','Z');DATA.write_text(json.dumps(d,indent=2,ensure_ascii=False))
if __name__=='__main__':main()