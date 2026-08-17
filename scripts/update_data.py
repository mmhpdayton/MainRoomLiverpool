import json,re,urllib.request,urllib.parse,xml.etree.ElementTree as ET,html
from html.parser import HTMLParser
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
DATA=ROOT/'site-data.json'
HEAD={'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126 Safari/537.36','Accept':'text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8','Accept-Language':'en-GB,en;q=0.9'}
COMPETITIONS={'eng.1':'Premier League','uefa.champions':'Champions League','eng.fa':'FA Cup','eng.league_cup':'Carabao Cup'}
LFC_FIXTURES='https://www.liverpoolfc.com/fixtures/mens/first-team'
PL_TABLE='https://www.premierleague.com/en/tables/premier-league/2026-27'
BBC_FIXTURES='https://www.bbc.co.uk/sport/football/teams/liverpool/scores-fixtures/{year}-{month:02d}'
BBC_TABLE='https://www.bbc.co.uk/sport/football/premier-league/table'
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
  return urllib.request.urlopen(urllib.request.Request(url,headers=h),timeout=30).read()
def getjson(url): return json.loads(request(url,True))
def gettext(url): return request(url).decode('utf-8','ignore')
def tokens(url): p=TextExtractor();p.feed(gettext(url));return p.tokens
def load(): return json.loads(DATA.read_text())
def norm_team(s): return ALIASES.get(s,s)
def slug(s): return re.sub('[^a-z0-9]+','-',s.lower()).strip('-')

def team_from_token(s):
  clean=' '.join(s.replace('\u00a0',' ').split())
  for name in sorted(set(PL_TEAMS)|set(ALIASES.keys()),key=len,reverse=True):
    if name.lower() in clean.lower():return norm_team(name)
  return None

def competition_name(s):
  x=s.lower()
  if 'premier league' in x:return 'Premier League'
  if 'champions league' in x:return 'Champions League'
  if 'fa cup' in x:return 'FA Cup'
  if 'league cup' in x or 'carabao' in x:return 'Carabao Cup'
  return None

def merge_fixture_meta(new,old):
  old_by_opp={}
  for x in old:old_by_opp.setdefault((x.get('opponent'),x.get('competition')),[]).append(x)
  for x in new:
    candidates=old_by_opp.get((x['opponent'],x['competition']),[])
    prior=min(candidates,key=lambda o:abs(datetime.fromisoformat(o['date'].replace('Z','+00:00')).timestamp()-datetime.fromisoformat(x['date'].replace('Z','+00:00')).timestamp()),default={})
    x['broadcastUS']=prior.get('broadcastUS') or 'TBA'
    if prior.get('broadcastUSSource'):x['broadcastUSSource']=prior['broadcastUSSource']
    if prior.get('broadcastUK'):x['broadcastUK']=prior['broadcastUK']
    if prior.get('venue') and not x.get('venue'):x['venue']=prior['venue']
  return new

def lfc_fixtures(old):
  t=tokens(LFC_FIXTURES);out=[];seen=set();months='January February March April May June July August September October November December';date_re=re.compile(r'^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)(?:day)?\s+(\d{1,2})\s+('+months.replace(' ','|')+r')(?:\s+—\s*(.*))?$');time_re=re.compile(r'^([01]?\d|2[0-3]):([0-5]\d)$');season_year={'August':2026,'September':2026,'October':2026,'November':2026,'December':2026,'January':2027,'February':2027,'March':2027,'April':2027,'May':2027,'June':2027,'July':2027}
  for i,v in enumerate(t):
    if v not in {'Premier League','Champions League','FA Cup','Carabao Cup'}:continue
    w=t[i:i+24];dm=next((date_re.match(s) for s in w if date_re.match(s)),None)
    if not dm:continue
    teams=[];time_hit=None
    for s in w:
      tm=team_from_token(s)
      if tm and (not teams or teams[-1]!=tm):teams.append(tm)
      if not time_hit and time_re.match(s):time_hit=s
    pair=next((teams[a:a+2] for a in range(len(teams)-1) if 'Liverpool' in teams[a:a+2] and teams[a]!=teams[a+1]),None)
    if not pair or not time_hit:continue
    first,second=pair;opp=second if first=='Liverpool' else first;day=int(dm.group(1));mon=dm.group(2);yr=season_year[mon];hh,mm=map(int,time_hit.split(':'));local=datetime.strptime(f'{yr}-{mon}-{day} {hh:02d}:{mm:02d}','%Y-%B-%d %H:%M').replace(tzinfo=ZoneInfo('Europe/London'));dt=local.astimezone(timezone.utc);key=(dt.isoformat(),opp,v)
    if key in seen:continue
    seen.add(key);out.append({'id':f'lfc-{dt.strftime("%Y%m%d%H%M")}-{slug(opp)}','date':dt.isoformat().replace('+00:00','Z'),'opponent':opp,'homeAway':'H' if first=='Liverpool' else 'A','competition':v,'venue':(dm.group(3) or '').strip(),'broadcastUS':'TBA','broadcastUSSource':'','status':'scheduled','scoreFor':None,'scoreAgainst':None,'fixtureSource':'Liverpool FC'})
  if len([x for x in out if x['competition']=='Premier League'])<30:raise RuntimeError(f'Liverpool FC parser found only {len(out)} fixtures')
  return merge_fixture_meta(sorted(out,key=lambda x:x['date']),old)

def bbc_fixtures(old):
  out=[];seen=set();date_re=re.compile(r'^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+(\d{1,2})(?:st|nd|rd|th)\s+(January|February|March|April|May|June|July|August|September|October|November|December)$');time_re=re.compile(r'^([01]?\d|2[0-3]):([0-5]\d)$')
  for year,month in [(2026,m) for m in range(8,13)]+[(2027,m) for m in range(1,6)]:
    t=tokens(BBC_FIXTURES.format(year=year,month=month));starts=[i for i,s in enumerate(t) if date_re.match(s)]
    for n,start in enumerate(starts):
      end=starts[n+1] if n+1<len(starts) else len(t);block=t[start:end];dm=date_re.match(block[0]);comp=next((competition_name(s) for s in block if competition_name(s)),None)
      if not comp:continue
      teams=[];time_hit=None;ft='FT' in block;scores=[]
      for s in block:
        tm=team_from_token(s)
        if tm and (not teams or teams[-1]!=tm):teams.append(tm)
        if not time_hit and time_re.match(s):time_hit=s
        if re.fullmatch(r'\d+',s):scores.append(int(s))
      pair=next((teams[a:a+2] for a in range(len(teams)-1) if 'Liverpool' in teams[a:a+2] and teams[a]!=teams[a+1]),None)
      if not pair:continue
      first,second=pair;opp=second if first=='Liverpool' else first;ha='H' if first=='Liverpool' else 'A';hh,mm=map(int,time_hit.split(':')) if time_hit else (15,0);day=int(dm.group(2));mon=dm.group(3);local=datetime.strptime(f'{year}-{mon}-{day} {hh:02d}:{mm:02d}','%Y-%B-%d %H:%M').replace(tzinfo=ZoneInfo('Europe/London'));dt=local.astimezone(timezone.utc);key=(dt.date().isoformat(),opp,comp)
      if key in seen:continue
      seen.add(key);sf=sa=None
      if ft and len(scores)>=2:sf=scores[0] if ha=='H' else scores[1];sa=scores[1] if ha=='H' else scores[0]
      out.append({'id':f'bbc-{dt.strftime("%Y%m%d%H%M")}-{slug(opp)}','date':dt.isoformat().replace('+00:00','Z'),'opponent':opp,'homeAway':ha,'competition':comp,'venue':'','broadcastUS':'TBA','broadcastUSSource':'','status':'final' if ft else 'scheduled','scoreFor':sf,'scoreAgainst':sa,'fixtureSource':'BBC Sport UK fallback'})
  pl=[x for x in out if x['competition']=='Premier League']
  if len(pl)<30:raise RuntimeError(f'BBC parser found only {len(out)} fixtures / {len(pl)} PL')
  return merge_fixture_meta(sorted(out,key=lambda x:x['date']),old)

def safe_bbc_overlay(bbc,old):
  # BBC is a cross-check, not authority for already-published PL dates/home-away.
  # Preserve the last Liverpool-confirmed PL schedule; use BBC for cup additions/results.
  result=[dict(x) for x in old];pl_old=[x for x in result if x.get('competition')=='Premier League']
  for b in bbc:
    if b.get('competition')=='Premier League':
      candidates=[x for x in pl_old if x.get('opponent')==b.get('opponent')]
      if not candidates:continue
      prior=min(candidates,key=lambda x:abs(datetime.fromisoformat(x['date'].replace('Z','+00:00')).timestamp()-datetime.fromisoformat(b['date'].replace('Z','+00:00')).timestamp()))
      delta=abs(datetime.fromisoformat(prior['date'].replace('Z','+00:00')).timestamp()-datetime.fromisoformat(b['date'].replace('Z','+00:00')).timestamp())
      # Only adopt a completed result when BBC's date is essentially the same known fixture.
      if b.get('status')=='final' and delta<=36*3600:
        prior['status']='final';prior['scoreFor']=b.get('scoreFor');prior['scoreAgainst']=b.get('scoreAgainst')
      continue
    key=(b.get('date','')[:10],b.get('opponent'),b.get('competition'))
    if not any((x.get('date','')[:10],x.get('opponent'),x.get('competition'))==key for x in result):result.append(b)
  return sorted(result,key=lambda x:x['date'])

def parse_table_tokens(t,source):
  out=[];aliases_by_team={team:[team] for team in PL_TEAMS};aliases_by_team['AFC Bournemouth']+=['Bournemouth'];aliases_by_team['Brighton & Hove Albion']+=['Brighton and Hove Albion','Brighton'];aliases_by_team['Manchester City']+=['Man City'];aliases_by_team['Manchester United']+=['Man Utd'];aliases_by_team['Nottingham Forest']+=["Nott'm Forest",'Nottm Forest'];aliases_by_team['Tottenham Hotspur']+=['Spurs'];aliases_by_team['Hull City']+=['Hull'];aliases_by_team['Ipswich Town']+=['Ipswich'];aliases_by_team['Newcastle United']+=['Newcastle'];aliases_by_team['Leeds United']+=['Leeds']
  for team in PL_TEAMS:
    best=None
    for i,s in enumerate(t):
      if not any(a.lower() in s.lower() for a in aliases_by_team[team]):continue
      nums=[int(z) for z in t[i+1:i+22] if re.fullmatch(r'-?\d+',z)]
      if len(nums)>=8:
        pos=next((int(z) for z in reversed(t[max(0,i-8):i]) if re.fullmatch(r'\d{1,2}',z)),len(out)+1);best=(pos,nums[:8]);break
    if best:
      pos,n=best;out.append({'pos':pos,'team':team,'p':n[0],'w':n[1],'d':n[2],'l':n[3],'gf':n[4],'ga':n[5],'gd':n[6],'pts':n[7],'tableSource':source})
  if len(out)<18:raise RuntimeError(f'{source} parser found only {len(out)} clubs')
  return sorted(out,key=lambda x:x['pos'])
def parse_pl_table():return parse_table_tokens(tokens(PL_TABLE),'Premier League')
def parse_bbc_table():return parse_table_tokens(tokens(BBC_TABLE),'BBC Sport UK fallback')

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
    status=(comp.get('status') or {}).get('type',{});done=status.get('completed',False);out.append({'id':str(ev.get('id')),'date':ev.get('date'),'opponent':opp.get('team',{}).get('displayName'),'homeAway':'H' if lfc.get('homeAway')=='home' else 'A','competition':COMPETITIONS.get(slug,slug),'venue':(comp.get('venue') or {}).get('fullName',''),'broadcastUS':normalize_broadcasts(slug,b),'broadcastUSSource':'ESPN match listing' if b else '','status':'final' if done else 'scheduled','scoreFor':lfc.get('score',{}).get('displayValue') if isinstance(lfc.get('score'),dict) else lfc.get('score'),'scoreAgainst':opp.get('score',{}).get('displayValue') if isinstance(opp.get('score'),dict) else opp.get('score'),'fixtureSource':'ESPN last-resort fallback'})
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
  try:fixtures=lfc_fixtures(old);health['fixtures']='Liverpool FC official'
  except Exception as e:
    print('LFC fixtures',e)
    try:fixtures=safe_bbc_overlay(bbc_fixtures(old),old);health['fixtures']='Liverpool-confirmed PL schedule + BBC UK cross-check'
    except Exception as be:
      print('BBC fixtures',be);fixtures=old;health['fixtures']='Liverpool-confirmed schedule preserved'
  if fixtures:d['fixtures']=sorted(fixtures,key=lambda x:x['date'])
  try:d['premierLeagueTable']=parse_pl_table();health['premierLeagueTable']='PremierLeague.com official'
  except Exception as e:
    print('PL table',e)
    try:d['premierLeagueTable']=parse_bbc_table();health['premierLeagueTable']='BBC Sport UK fallback'
    except Exception as be:print('BBC table',be);health['premierLeagueTable']='stale fallback'
  n=news()
  if n:d['news']=n
  d['dataSources']={'fixtures':'Liverpool FC official schedule; BBC Sport UK used only as cross-check/result/cup fallback','premierLeagueTable':'PremierLeague.com official → BBC Sport UK fallback','broadcastUS':'match-specific U.S. rights listings / preserved confirmations','lastResort':'ESPN is not required for core site operation'};d['dataHealth']=health;d['updated']=datetime.now(timezone.utc).isoformat().replace('+00:00','Z');DATA.write_text(json.dumps(d,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
