import json,re,urllib.request,urllib.parse,xml.etree.ElementTree as ET,html
from html.parser import HTMLParser
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
DATA=ROOT/'site-data.json'
HEAD={'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126 Safari/537.36','Accept':'text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8','Accept-Language':'en-GB,en;q=0.9'}
LFC_FIXTURES='https://www.liverpoolfc.com/fixtures/mens/first-team'
PL_TABLE='https://www.premierleague.com/en/tables/premier-league/2026-27'
BBC_TABLE='https://www.bbc.co.uk/sport/football/premier-league/table'
NBC_PL_HUB='https://www.nbcsports.com/pressbox/premier-league'
CBS_UCL='https://www.cbssports.com/soccer/champions-league/schedule/'
CBS_CARABAO='https://www.cbssports.com/soccer/carabao-cup/schedule/'
ESPN_FA='https://www.espn.com/soccer/schedule/_/league/eng.fa'
PL_TEAMS=['Arsenal','Aston Villa','AFC Bournemouth','Brentford','Brighton & Hove Albion','Chelsea','Coventry City','Crystal Palace','Everton','Fulham','Hull City','Ipswich Town','Leeds United','Liverpool','Manchester City','Manchester United','Newcastle United','Nottingham Forest','Sunderland','Tottenham Hotspur']
ALIASES={'Bournemouth':'AFC Bournemouth','Brighton and Hove Albion':'Brighton & Hove Albion','Brighton':'Brighton & Hove Albion','Man City':'Manchester City','Man Utd':'Manchester United','Nottm Forest':'Nottingham Forest',"Nott'm Forest":'Nottingham Forest','Spurs':'Tottenham Hotspur','Hull':'Hull City','Ipswich':'Ipswich Town','Newcastle':'Newcastle United','Leeds':'Leeds United','Coventry':'Coventry City'}
COMPS={'Premier League':'Premier League','Champions League':'Champions League','Emirates FA Cup':'FA Cup','FA Cup':'FA Cup','Carabao Cup':'Carabao Cup'}

class PageParser(HTMLParser):
  def __init__(self):super().__init__();self.tokens=[];self.links=[];self.skip=0
  def handle_starttag(self,tag,attrs):
    if tag in ('script','style','noscript'):self.skip+=1
    if tag=='a':
      href=dict(attrs).get('href')
      if href:self.links.append(href)
  def handle_endtag(self,tag):
    if tag in ('script','style','noscript') and self.skip:self.skip-=1
  def handle_data(self,data):
    if not self.skip:
      s=' '.join(html.unescape(data).split())
      if s:self.tokens.append(s)

def request(url):return urllib.request.urlopen(urllib.request.Request(url,headers=HEAD),timeout=30).read()
def page(url):
  p=PageParser();p.feed(request(url).decode('utf-8','ignore'));return p

def norm_team(s):return ALIASES.get(s,s)
def team_from_token(s):
  clean=' '.join(s.replace('\u00a0',' ').split())
  for name in sorted(set(PL_TEAMS)|set(ALIASES),key=len,reverse=True):
    if name.lower()==clean.lower() or name.lower() in clean.lower():return norm_team(name)
  return None

def slug(s):return re.sub('[^a-z0-9]+','-',s.lower()).strip('-')

def parse_lfc_fixtures():
  t=page(LFC_FIXTURES).tokens;out=[];seen=set();date_re=re.compile(r'^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+—\s+(.+)$');time_re=re.compile(r'^([01]?\d|2[0-3]):([0-5]\d)$')
  years={'August':2026,'September':2026,'October':2026,'November':2026,'December':2026,'January':2027,'February':2027,'March':2027,'April':2027,'May':2027,'June':2027,'July':2027}
  for i,s in enumerate(t):
    comp=COMPS.get(s)
    if not comp:continue
    w=t[i:i+22];dm=next((date_re.match(z) for z in w if date_re.match(z)),None)
    if not dm:continue
    teams=[];kick=None
    for z in w:
      tm=team_from_token(z)
      if tm and (not teams or teams[-1]!=tm):teams.append(tm)
      if kick is None and time_re.match(z):kick=z
    pair=next((teams[j:j+2] for j in range(len(teams)-1) if 'Liverpool' in teams[j:j+2] and teams[j]!=teams[j+1]),None)
    if not pair or not kick:continue
    first,second=pair;opp=second if first=='Liverpool' else first;ha='H' if first=='Liverpool' else 'A';mon=dm.group(3);yr=years[mon];day=int(dm.group(2));hh,mm=map(int,kick.split(':'));local=datetime.strptime(f'{yr}-{mon}-{day} {hh:02d}:{mm:02d}','%Y-%B-%d %H:%M').replace(tzinfo=ZoneInfo('Europe/London'));dt=local.astimezone(timezone.utc)
    key=(comp,opp,ha)
    if key in seen:continue
    seen.add(key);out.append({'id':f'lfc-{dt.strftime("%Y%m%d%H%M")}-{slug(opp)}','date':dt.isoformat().replace('+00:00','Z'),'opponent':opp,'homeAway':ha,'competition':comp,'venue':dm.group(4).strip(),'broadcastUS':'TBA','broadcastUSSource':'','status':'scheduled','scoreFor':None,'scoreAgainst':None,'fixtureSource':'Liverpool FC official'})
  return sorted(out,key=lambda x:x['date'])

def guarded_fixture_refresh(old):
  fresh=parse_lfc_fixtures();pl=[x for x in fresh if x['competition']=='Premier League'];oldpl=[x for x in old if x.get('competition')=='Premier League']
  # Only trust PL replacement when the official page yields essentially the full season and the same opponent/home-away identity map.
  old_ids={(x.get('opponent'),x.get('homeAway')) for x in oldpl};new_ids={(x.get('opponent'),x.get('homeAway')) for x in pl}
  if len(pl)>=36 and old_ids and not old_ids.issubset(new_ids):
    raise RuntimeError('Liverpool FC PL identity check failed; preserving known-good PL schedule')
  final=[]
  if len(pl)>=36:final+=pl
  else:final+=oldpl
  # Non-PL matches are additive/reconciling only when Liverpool FC publishes a named opponent and kickoff.
  old_other=[x for x in old if x.get('competition')!='Premier League']
  fresh_other=[x for x in fresh if x['competition']!='Premier League' and x.get('opponent') not in ('TBC','TBA','')]
  bykey={(x.get('competition'),x.get('opponent'),x.get('homeAway')):x for x in old_other}
  for x in fresh_other:bykey[(x['competition'],x['opponent'],x['homeAway'])]=x
  final+=bykey.values()
  # Preserve confirmed broadcast metadata by competition/opponent/home-away.
  oldmeta={(x.get('competition'),x.get('opponent'),x.get('homeAway')):x for x in old}
  for x in final:
    p=oldmeta.get((x.get('competition'),x.get('opponent'),x.get('homeAway')),{})
    if p.get('broadcastUS') and p.get('broadcastUS')!='TBA':x['broadcastUS']=p['broadcastUS']
    if p.get('broadcastUSSource'):x['broadcastUSSource']=p['broadcastUSSource']
    if p.get('broadcastCheckedAt'):x['broadcastCheckedAt']=p['broadcastCheckedAt']
  return sorted(final,key=lambda x:x['date']),('Liverpool FC official' if len(pl)>=36 else 'PL preserved; LFC cup/UCL additions only')

def parse_table_tokens(t,source):
  aliases={team:[team] for team in PL_TEAMS}
  for a,b in ALIASES.items():aliases.setdefault(b,[b]).append(a)
  out=[]
  for team in PL_TEAMS:
    best=None
    for i,s in enumerate(t):
      if not any(a.lower() in s.lower() for a in aliases[team]):continue
      nums=[int(z) for z in t[i+1:i+22] if re.fullmatch(r'-?\d+',z)]
      if len(nums)>=8:
        pos=next((int(z) for z in reversed(t[max(0,i-8):i]) if re.fullmatch(r'\d{1,2}',z)),len(out)+1);best=(pos,nums[:8]);break
    if best:
      pos,n=best;out.append({'pos':pos,'team':team,'p':n[0],'w':n[1],'d':n[2],'l':n[3],'gf':n[4],'ga':n[5],'gd':n[6],'pts':n[7],'tableSource':source})
  if len(out)<18:raise RuntimeError(f'{source} parser found only {len(out)} clubs')
  return sorted(out,key=lambda x:x['pos'])

def outlet_scan(tokens,fixture,allowed):
  opp=fixture['opponent'];matches=[]
  for i,s in enumerate(tokens):
    low=s.lower()
    if 'liverpool' in low and any(part.lower() in low for part in [opp,opp.replace('AFC ','')]):matches.append(i)
    elif team_from_token(s)==opp:
      w=' '.join(tokens[max(0,i-8):i+9]).lower()
      if 'liverpool' in w:matches.append(i)
  found=[]
  for i in matches:
    w=' | '.join(tokens[max(0,i-14):i+15])
    for name in allowed:
      if name.lower() in w.lower() and name not in found:found.append(name)
  return found

def nbc_pressbox_outlets(fixture):
  hub=page(NBC_PL_HUB);urls=[]
  for h in hub.links:
    if '/pressbox/press-releases/' in h:
      u=urllib.parse.urljoin(NBC_PL_HUB,h)
      if u not in urls:urls.append(u)
  allowed=['NBC','USA Network','Peacock','NBCSN','CNBC','SYFY']
  for u in urls[:18]:
    try:
      p=page(u);f=outlet_scan(p.tokens,fixture,allowed)
      if f:return f,u
    except Exception:pass
  return [],''

def cbs_schedule_outlets(url,fixture):
  try:
    t=page(url).tokens;allowed=['CBS','CBS Sports Network','CBS Sports Golazo Network','Paramount+'];f=outlet_scan(t,fixture,allowed);return f,url if f else ''
  except Exception:return [],''

def espn_fa_outlets(fixture):
  try:
    t=page(ESPN_FA).tokens;allowed=['ESPN','ESPN2','ESPN+','ESPN Deportes'];f=outlet_scan(t,fixture,allowed);return f,ESPN_FA if f else ''
  except Exception:return [],''

def refresh_broadcasts(fixtures):
  now=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
  for x in fixtures:
    comp=x.get('competition');found=[];src=''
    if comp=='Premier League':found,src=nbc_pressbox_outlets(x)
    elif comp=='Champions League':
      found,src=cbs_schedule_outlets(CBS_UCL,x)
      if 'Paramount+' not in found:found=['Paramount+']+found;src=src or 'Paramount Press Express — every UEFA match streams on Paramount+'
    elif comp=='Carabao Cup':found,src=cbs_schedule_outlets(CBS_CARABAO,x)
    elif comp=='FA Cup':found,src=espn_fa_outlets(x)
    if found:
      x['broadcastUS']=' • '.join(dict.fromkeys(found));x['broadcastUSSource']=src;x['broadcastCheckedAt']=now;x['broadcastConfidence']='official match-specific' if src.startswith('http') else 'official rights baseline'
    elif not x.get('broadcastUS'):
      x['broadcastUS']='TBA';x['broadcastCheckedAt']=now
  return fixtures

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
  d=json.loads(DATA.read_text());health={}
  try:d['fixtures'],health['fixtures']=guarded_fixture_refresh(d.get('fixtures',[]))
  except Exception as e:print('fixtures',e);health['fixtures']='preserved last-known-good schedule'
  try:d['fixtures']=refresh_broadcasts(d.get('fixtures',[]));health['broadcastUS']='official rights-holder scan completed'
  except Exception as e:print('broadcasts',e);health['broadcastUS']='preserved confirmed broadcast data'
  try:d['premierLeagueTable']=parse_table_tokens(page(PL_TABLE).tokens,'PremierLeague.com official');health['premierLeagueTable']='PremierLeague.com official'
  except Exception as e:
    print('PL table',e)
    try:d['premierLeagueTable']=parse_table_tokens(page(BBC_TABLE).tokens,'BBC Sport UK fallback');health['premierLeagueTable']='BBC Sport UK fallback'
    except Exception as be:print('BBC table',be);health['premierLeagueTable']='preserved last-known-good table'
  n=news()
  if n:d['news']=n
  d['dataSources']={'fixtures':'Liverpool FC official, guarded against identity drift','premierLeagueTable':'PremierLeague.com official → BBC Sport fallback','broadcastUS':'NBC Sports Press Box / CBS Sports schedules / ESPN match schedule; Paramount+ baseline for UCL only'}
  d['dataHealth']=health;d['updated']=datetime.now(timezone.utc).isoformat().replace('+00:00','Z');DATA.write_text(json.dumps(d,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
