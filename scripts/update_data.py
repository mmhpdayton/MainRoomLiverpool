import json,re,urllib.request,urllib.parse,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
DATA=ROOT/'site-data.json'
HEAD={'User-Agent':'Mozilla/5.0 MainRoomLiverpool/1.0'}
COMPETITIONS={
  'eng.1':'Premier League',
  'uefa.champions':'Champions League',
  'eng.fa':'FA Cup',
  'eng.league_cup':'Carabao Cup'
}
def getjson(url):
    req=urllib.request.Request(url,headers=HEAD);return json.loads(urllib.request.urlopen(req,timeout=25).read())
def gettext(url):
    req=urllib.request.Request(url,headers=HEAD);return urllib.request.urlopen(req,timeout=25).read()
def load(): return json.loads(DATA.read_text())
def normalize_broadcasts(slug,names):
    names=list(dict.fromkeys([n.strip() for n in names if n and n.strip()]))
    if slug=='eng.fa' and 'ESPN+' not in names: names.append('ESPN+')
    if names:return ' • '.join(names)
    if slug=='uefa.champions':return 'Paramount+'
    return 'TBA'
def espn_fixtures(slug):
    j=getjson(f'https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/teams/364/schedule?season=2026')
    out=[]
    for ev in j.get('events',[]):
      comp=(ev.get('competitions') or [{}])[0];cs=comp.get('competitors',[]);lfc=next((c for c in cs if str(c.get('team',{}).get('id'))=='364'),None);opp=next((c for c in cs if c is not lfc),None)
      if not lfc or not opp: continue
      status=(comp.get('status') or {}).get('type',{});done=status.get('completed',False)
      b=[]
      for br in comp.get('broadcasts',[]) or []: b += br.get('names',[]) or []
      broadcast=normalize_broadcasts(slug,b)
      out.append({'id':str(ev.get('id')),'date':ev.get('date'),'opponent':opp.get('team',{}).get('displayName'),'homeAway':'H' if lfc.get('homeAway')=='home' else 'A','competition':COMPETITIONS.get(slug,slug),'venue':(comp.get('venue') or {}).get('fullName',''),'broadcastUS':broadcast,'broadcastUSSource':'ESPN match listing' if b else ('U.S. rights package' if broadcast!='TBA' else ''),'status':'final' if done else 'scheduled','scoreFor':lfc.get('score',{}).get('displayValue') if isinstance(lfc.get('score'),dict) else lfc.get('score'),'scoreAgainst':opp.get('score',{}).get('displayValue') if isinstance(opp.get('score'),dict) else opp.get('score')})
    return out
def statval(stats,*names,default=0):
    for name in names:
      if name in stats and stats[name] is not None:return stats[name]
    return default
def standings(slug):
    j=getjson(f'https://site.api.espn.com/apis/v2/sports/soccer/{slug}/standings?season=2026')
    groups=j.get('children') or [j];entries=[]
    for g in groups:
      st=(g.get('standings') or {}).get('entries',[])
      if len(st)>len(entries): entries=st
    out=[]
    for e in entries:
      team=e.get('team',{});stats={s.get('name'):s.get('value') for s in e.get('stats',[])}
      gf=int(statval(stats,'pointsFor','goalsFor','for',default=0) or 0)
      ga=int(statval(stats,'pointsAgainst','goalsAgainst','against',default=0) or 0)
      gd=int(statval(stats,'pointDifferential','goalDifference',default=gf-ga) or 0)
      logos=team.get('logos') or []
      out.append({'pos':int(statval(stats,'rank',default=len(out)+1) or len(out)+1),'team':team.get('displayName'),'teamId':str(team.get('id') or ''),'logo':(logos[0].get('href') if logos else ''),'color':team.get('color') or '999999','alternateColor':team.get('alternateColor') or 'ffffff','p':int(statval(stats,'gamesPlayed',default=0) or 0),'w':int(statval(stats,'wins',default=0) or 0),'d':int(statval(stats,'ties','draws',default=0) or 0),'l':int(statval(stats,'losses',default=0) or 0),'gf':gf,'ga':ga,'gd':gd,'pts':int(statval(stats,'points',default=0) or 0)})
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
  old_by_key={(x['date'][:10],x['opponent'],x.get('competition')):x for x in old}
  uk_confirmed={('2026-08-23','Newcastle United'):'Sky Sports',('2026-08-29','Nottingham Forest'):'TNT Sports',('2026-09-04','Ipswich Town'):'Sky Sports',('2026-09-20','AFC Bournemouth'):'Sky Sports'}
  for x in new:
    key3=(x['date'][:10],x['opponent'],x.get('competition'));prior=old_by_key.get(key3,{});key2=(x['date'][:10],x['opponent'])
    if prior.get('broadcastUS') not in (None,'','TBA') and x.get('broadcastUS') in ('',None,'TBA'):
      x['broadcastUS']=prior['broadcastUS'];x['broadcastUSSource']=prior.get('broadcastUSSource','Previous confirmed listing')
    if prior.get('broadcastUK'): x['broadcastUK']=prior['broadcastUK']
    if key2 in uk_confirmed: x['broadcastUK']=uk_confirmed[key2]
    if key2==('2026-08-23','Newcastle United') and x.get('competition')=='Premier League':
      x['broadcastUS']='USA Network';x['broadcastUSSource']='NBC Sports'
  return new
def main():
  d=load();old=d.get('fixtures',[]);fixtures=[]
  for slug,label in COMPETITIONS.items():
    try:fixtures+=merge_broadcasts(espn_fixtures(slug),old)
    except Exception as e:print(label,'fixtures',e);fixtures += [x for x in old if x.get('competition')==label]
  fixtures += [x for x in old if x.get('competition') not in set(COMPETITIONS.values())]
  dedup={}
  for x in fixtures:
    k=x.get('id') or (x.get('date'),x.get('opponent'),x.get('competition'));dedup[k]=x
  if dedup:d['fixtures']=sorted(dedup.values(),key=lambda x:x['date'])
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