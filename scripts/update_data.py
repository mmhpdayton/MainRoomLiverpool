import json,re,urllib.request,urllib.parse,xml.etree.ElementTree as ET,html
from html.parser import HTMLParser
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
DATA=ROOT/'site-data.json'
HEAD={
  'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126 Safari/537.36',
  'Accept':'text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8',
  'Accept-Language':'en-US,en;q=0.9'
}
COMPETITIONS={'eng.1':'Premier League','uefa.champions':'Champions League','eng.fa':'FA Cup','eng.league_cup':'Carabao Cup'}
LFC_FIXTURES='https://www.liverpoolfc.com/fixtures/mens/first-team'
PL_TABLE='https://www.premierleague.com/en/tables/premier-league/2026-27'
PL_TEAMS=['Arsenal','Aston Villa','AFC Bournemouth','Brentford','Brighton & Hove Albion','Chelsea','Coventry City','Crystal Palace','Everton','Fulham','Hull City','Ipswich Town','Leeds United','Liverpool','Manchester City','Manchester United','Newcastle United','Nottingham Forest','Sunderland','Tottenham Hotspur']
ALIASES={'Bournemouth':'AFC Bournemouth','Brighton and Hove Albion':'Brighton & Hove Albion','Brighton':'Brighton & Hove Albion','Man City':'Manchester City','Man Utd':'Manchester United','Nottm Forest':'Nottingham Forest','Nott\'m Forest':'Nottingham Forest','Spurs':'Tottenham Hotspur','Hull':'Hull City','Ipswich':'Ipswich Town','Newcastle':'Newcastle United','Leeds':'Leeds United'}

class TextExtractor(HTMLParser):
  def __init__(self): super().__init__();self.tokens=[];self.skip=0
  def handle_starttag(self,tag,attrs):
    if tag in ('script','style','noscript'): self.skip+=1
  def handle_endtag(self,tag):
    if tag in ('script','style','noscript') and self.skip:self.skip-=1
  def handle_data(self,data):
    if not self.skip:
      s=' '.join(html.unescape(data).split())
      if s:self.tokens.append(s)

def request(url,accept_json=False):
  h=dict(HEAD)
  if accept_json:h['Accept']='application/json,text/plain,*/*'
  req=urllib.request.Request(url,headers=h)
  return urllib.request.urlopen(req,timeout=30).read()

def getjson(url): return json.loads(request(url,True))
def gettext(url): return request(url).decode('utf-8','ignore')
def tokens(url):
  p=TextExtractor();p.feed(gettext(url));return p.tokens

def load(): return json.loads(DATA.read_text())
def norm_team(s): return ALIASES.get(s,s)

def merge_fixture_meta(new,old):
  old_by_opp={}
  for x in old: old_by_opp.setdefault((x.get('opponent'),x.get('competition')),[]).append(x)
  for x in new:
    candidates=old_by_opp.get((x['opponent'],x['competition']),[])
    prior=min(candidates,key=lambda o:abs(datetime.fromisoformat(o['date'].replace('Z','+00:00')).timestamp()-datetime.fromisoformat(x['date'].replace('Z','+00:00')).timestamp()),default={})
    if prior.get('broadcastUS'): x['broadcastUS']=prior['broadcastUS']
    else:x['broadcastUS']='TBA'
    if prior.get('broadcastUSSource'):x['broadcastUSSource']=prior['broadcastUSSource']
    if prior.get('broadcastUK'):x['broadcastUK']=prior['broadcastUK']
    if prior.get('status')=='final':
      x['status']='final';x['scoreFor']=prior.get('scoreFor');x['scoreAgainst']=prior.get('scoreAgainst')
  return new

def lfc_fixtures(old):
  t=tokens(LFC_FIXTURES);out=[];seen=set()
  comp_names={'Premier League','Champions League','FA Cup','Carabao Cup'}
  months='January February March April May June July August September October November December'
  date_re=re.compile(r'^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)(?:day)?\s+(\d{1,2})\s+('+months.replace(' ','|')+r')(?:\s+—\s*(.*))?$')
  time_re=re.compile(r'^([01]?\d|2[0-3]):([0-5]\d)$')
  season_year={'August':2026,'September':2026,'October':2026,'November':2026,'December':2026,'January':2027,'February':2027,'March':2027,'April':2027,'May':2027,'June':2027,'July':2027}
  known=set(PL_TEAMS)|set(ALIASES.keys())|{'Liverpool'}
  for i,v in enumerate(t):
    if v not in comp_names:continue
    w=t[i:i+18];date_idx=None;dm=None
    for j,s in enumerate(w):
      m=date_re.match(s)
      if m:date_idx=j;dm=m;break
    if dm is None:continue
    team_hits=[];time_hit=None
    for j,s in enumerate(w):
      ns=norm_team(s)
      if ns in known or ns in PL_TEAMS: team_hits.append((j,norm_team(s)))
      if time_hit is None and time_re.match(s):time_hit=(j,s)
    # de-duplicate adjacent repeated team labels caused by image alt text
    compact=[]
    for hit in team_hits:
      if not compact or compact[-1][1]!=hit[1]:compact.append(hit)
    if len(compact)<2 or not any(x[1]=='Liverpool' for x in compact) or not time_hit:continue
    pair=None
    for a in range(len(compact)-1):
      p=compact[a:a+2]
      if any(x[1]=='Liverpool' for x in p) and p[0][1]!=p[1][1]:pair=p;break
    if not pair:continue
    first,second=pair[0][1],pair[1][1];opp=second if first=='Liverpool' else first
    if opp=='Liverpool':continue
    day=int(dm.group(1));mon=dm.group(2);yr=season_year.get(mon,2026)
    hh,mm=map(int,time_hit[1].split(':'));local=datetime.strptime(f'{yr}-{mon}-{day} {hh:02d}:{mm:02d}', '%Y-%B-%d %H:%M').replace(tzinfo=ZoneInfo('Europe/London'));dt=local.astimezone(timezone.utc)
    venue=(dm.group(3) or '').strip();ha='H' if first=='Liverpool' else 'A';key=(dt.isoformat(),opp,v)
    if key in seen:continue
    seen.add(key);out.append({'id':f'lfc-{dt.strftime("%Y%m%d%H%M")}-{re.sub("[^a-z0-9]+","-",opp.lower()).strip("-")}','date':dt.isoformat().replace('+00:00','Z'),'opponent':opp,'homeAway':ha,'competition':v,'venue':venue,'broadcastUS':'TBA','broadcastUSSource':'','status':'scheduled','scoreFor':None,'scoreAgainst':None,'fixtureSource':'Liverpool FC'})
  if len([x for x in out if x['competition']=='Premier League'])<30: raise RuntimeError(f'Liverpool FC parser found only {len(out)} fixtures')
  return merge_fixture_meta(sorted(out,key=lambda x:x['date']),old)

def parse_pl_table():
  t=tokens(PL_TABLE);out=[]
  # Find each team's occurrence that is followed by the nine full-table numeric fields.
  aliases_by_team={team:[team] for team in PL_TEAMS}
  aliases_by_team['AFC Bournemouth']+=['Bournemouth'];aliases_by_team['Brighton & Hove Albion']+=['Brighton and Hove Albion','Brighton'];aliases_by_team['Manchester City']+=['Man City'];aliases_by_team['Manchester United']+=['Man Utd'];aliases_by_team['Nottingham Forest']+=["Nott'm Forest",'Nottm Forest'];aliases_by_team['Tottenham Hotspur']+=['Spurs'];aliases_by_team['Hull City']+=['Hull'];aliases_by_team['Ipswich Town']+=['Ipswich'];aliases_by_team['Newcastle United']+=['Newcastle'];aliases_by_team['Leeds United']+=['Leeds']
  for team in PL_TEAMS:
    best=None
    for i,s in enumerate(t):
      if s not in aliases_by_team[team]:continue
      nums=[]
      for z in t[i+1:i+18]:
        if re.fullmatch(r'-?\d+',z):nums.append(int(z))
      if len(nums)>=8:
        # row numeric order: played,w,d,l,gf,ga,gd,pts (position is before team)
        pos=None
        for z in reversed(t[max(0,i-5):i]):
          if re.fullmatch(r'\d{1,2}',z):pos=int(z);break
        best=(pos or len(out)+1,nums[:8]);break
    if best:
      pos,n=best;out.append({'pos':pos,'team':team,'p':n[0],'w':n[1],'d':n[2],'l':n[3],'gf':n[4],'ga':n[5],'gd':n[6],'pts':n[7],'tableSource':'Premier League'})
  if len(out)<18:raise RuntimeError(f'Premier League parser found only {len(out)} clubs')
  return sorted(out,key=lambda x:x['pos'])

def normalize_broadcasts(slug,names):
  names=list(dict.fromkeys([n.strip() for n in names if n and n.strip()]))
  if slug=='eng.fa' and 'ESPN+' not in names:names.append('ESPN+')
  if names:return ' • '.join(names)
  if slug=='uefa.champions':return 'Paramount+'
  return 'TBA'

def espn_fixtures(slug):
  j=getjson(f'https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/teams/364/schedule?season=2026');out=[]
  for ev in j.get('events',[]):
    comp=(ev.get('competitions') or [{}])[0];cs=comp.get('competitors',[]);lfc=next((c for c in cs if str(c.get('team',{}).get('id'))=='364'),None);opp=next((c for c in cs if c is not lfc),None)
    if not lfc or not opp:continue
    b=[]
    for br in comp.get('broadcasts',[]) or []:b+=br.get('names',[]) or []
    status=(comp.get('status') or {}).get('type',{});done=status.get('completed',False)
    out.append({'id':str(ev.get('id')),'date':ev.get('date'),'opponent':opp.get('team',{}).get('displayName'),'homeAway':'H' if lfc.get('homeAway')=='home' else 'A','competition':COMPETITIONS.get(slug,slug),'venue':(comp.get('venue') or {}).get('fullName',''),'broadcastUS':normalize_broadcasts(slug,b),'broadcastUSSource':'ESPN match listing' if b else '','status':'final' if done else 'scheduled','scoreFor':lfc.get('score',{}).get('displayValue') if isinstance(lfc.get('score'),dict) else lfc.get('score'),'scoreAgainst':opp.get('score',{}).get('displayValue') if isinstance(opp.get('score'),dict) else opp.get('score'),'fixtureSource':'ESPN fallback'})
  return out

def news():
  sources=[('The Anfield Wrap','theanfieldwrap.com'),('The Athletic','nytimes.com/athletic'),('BBC','bbc.com/sport'),('Liverpool FC','liverpoolfc.com/news'),('The Guardian','theguardian.com/football'),('Reuters','reuters.com/sports/soccer'),('Liverpool Offside','liverpooloffside.sbnation.com')];items=[]
  for label,site in sources:
    try:
      q=urllib.parse.quote(f'Liverpool FC site:{site}');root=ET.fromstring(request(f'https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en'))
      for it in root.findall('.//item')[:3]:
        title=(it.findtext('title') or '').strip();link=(it.findtext('link') or '').strip();pub=(it.findtext('pubDate') or '').strip()
        if 'sun' in title.lower() and 'sunderland' not in title.lower():continue
        try:dt=datetime.strptime(pub,'%a, %d %b %Y %H:%M:%S %Z').replace(tzinfo=timezone.utc).isoformat().replace('+00:00','Z')
        except:dt=''
        items.append({'title':re.sub(r'\s+-\s+[^-]+$','',title),'source':label,'url':link,'published':dt})
    except Exception as e:print('news',label,e)
  items.sort(key=lambda x:x.get('published',''),reverse=True);return items[:18]

def main():
  d=load();old=d.get('fixtures',[]);health={};fixtures=None
  try:
    fixtures=lfc_fixtures(old);health['fixtures']='Liverpool FC'
  except Exception as e:
    print('LFC fixtures',e);health['fixtures']='Liverpool FC failed'
    # ESPN is fallback only. If it is blocked too, keep known-good data.
    try:
      pieces=[]
      for slug in COMPETITIONS:pieces+=espn_fixtures(slug)
      if pieces:fixtures=merge_fixture_meta(pieces,old);health['fixtures']='ESPN fallback'
    except Exception as ee:print('ESPN fallback',ee);health['fixtures']='stale fallback'
  if fixtures:d['fixtures']=sorted(fixtures,key=lambda x:x['date'])
  try:
    d['premierLeagueTable']=parse_pl_table();health['premierLeagueTable']='PremierLeague.com'
  except Exception as e:
    print('PL table',e);health['premierLeagueTable']='stale fallback'
  # Champions League table remains empty until the league-phase draw/table exists; preserve prior data.
  n=news()
  if n:d['news']=n
  d['dataSources']={'fixtures':'Liverpool FC official fixtures','premierLeagueTable':'Premier League official table','broadcastUS':'match-specific rights listings / preserved confirmations','fallback':'ESPN only if official fixture parsing fails'}
  d['dataHealth']=health;d['updated']=datetime.now(timezone.utc).isoformat().replace('+00:00','Z');DATA.write_text(json.dumps(d,indent=2,ensure_ascii=False))
  if health.get('fixtures')=='stale fallback' and health.get('premierLeagueTable')=='stale fallback':raise SystemExit('Both primary sports-data refreshes failed; old data preserved.')
if __name__=='__main__':main()
