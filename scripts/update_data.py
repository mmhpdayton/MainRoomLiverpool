import json,re,urllib.request,urllib.parse,xml.etree.ElementTree as ET,html
from html.parser import HTMLParser
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
DATA=ROOT/'site-data.json'
HEAD={'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126 Safari/537.36','Accept':'text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8','Accept-Language':'en-GB,en;q=0.9'}
PL_TABLE='https://www.premierleague.com/en/tables/premier-league/2026-27'
BBC_TABLE='https://www.bbc.co.uk/sport/football/premier-league/table'
PL_TEAMS=['Arsenal','Aston Villa','AFC Bournemouth','Brentford','Brighton & Hove Albion','Chelsea','Coventry City','Crystal Palace','Everton','Fulham','Hull City','Ipswich Town','Leeds United','Liverpool','Manchester City','Manchester United','Newcastle United','Nottingham Forest','Sunderland','Tottenham Hotspur']

class TextExtractor(HTMLParser):
  def __init__(self): super().__init__();self.tokens=[];self.skip=0
  def handle_starttag(self,tag,attrs):
    if tag in ('script','style','noscript'):self.skip+=1
  def handle_endtag(self,tag):
    if tag in ('script','style','noscript') and self.skip:self.skip-=1
  def handle_data(self,data):
    if not self.skip:
      s=' '.join(html.unescape(data).split())
      if s:self.tokens.append(s)

def request(url):
  return urllib.request.urlopen(urllib.request.Request(url,headers=HEAD),timeout=30).read()
def gettext(url):return request(url).decode('utf-8','ignore')
def tokens(url):p=TextExtractor();p.feed(gettext(url));return p.tokens

def parse_table_tokens(t,source):
  aliases={team:[team] for team in PL_TEAMS}
  aliases['AFC Bournemouth']+=['Bournemouth'];aliases['Brighton & Hove Albion']+=['Brighton and Hove Albion','Brighton'];aliases['Manchester City']+=['Man City'];aliases['Manchester United']+=['Man Utd'];aliases['Nottingham Forest']+=["Nott'm Forest",'Nottm Forest'];aliases['Tottenham Hotspur']+=['Spurs'];aliases['Hull City']+=['Hull'];aliases['Ipswich Town']+=['Ipswich'];aliases['Newcastle United']+=['Newcastle'];aliases['Leeds United']+=['Leeds']
  out=[]
  for team in PL_TEAMS:
    best=None
    for i,s in enumerate(t):
      if not any(a.lower() in s.lower() for a in aliases[team]):continue
      nums=[int(z) for z in t[i+1:i+22] if re.fullmatch(r'-?\d+',z)]
      if len(nums)>=8:
        pos=next((int(z) for z in reversed(t[max(0,i-8):i]) if re.fullmatch(r'\d{1,2}',z)),len(out)+1)
        best=(pos,nums[:8]);break
    if best:
      pos,n=best;out.append({'pos':pos,'team':team,'p':n[0],'w':n[1],'d':n[2],'l':n[3],'gf':n[4],'ga':n[5],'gd':n[6],'pts':n[7],'tableSource':source})
  if len(out)<18:raise RuntimeError(f'{source} parser found only {len(out)} clubs')
  return sorted(out,key=lambda x:x['pos'])

def news():
  sources=[('The Anfield Wrap','theanfieldwrap.com'),('The Athletic','nytimes.com/athletic'),('BBC','bbc.com/sport'),('Liverpool FC','liverpoolfc.com/news'),('The Guardian','theguardian.com/football'),('Reuters','reuters.com/sports/soccer'),('Liverpool Offside','liverpooloffside.sbnation.com')]
  items=[]
  for label,site in sources:
    try:
      q=urllib.parse.quote(f'Liverpool FC site:{site}')
      root=ET.fromstring(request(f'https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en'))
      for it in root.findall('.//item')[:3]:
        title=(it.findtext('title') or '').strip();link=(it.findtext('link') or '').strip();pub=(it.findtext('pubDate') or '').strip()
        if 'sun' in title.lower() and 'sunderland' not in title.lower():continue
        try:dt=datetime.strptime(pub,'%a, %d %b %Y %H:%M:%S %Z').replace(tzinfo=timezone.utc).isoformat().replace('+00:00','Z')
        except:dt=''
        items.append({'title':re.sub(r'\s+-\s+[^-]+$','',title),'source':label,'url':link,'published':dt})
    except Exception as e:print('news',label,e)
  items.sort(key=lambda x:x.get('published',''),reverse=True)
  return items[:18]

def main():
  d=json.loads(DATA.read_text())
  health={'fixtures':'LOCKED — verified Liverpool schedule; updater does not modify fixtures'}
  try:
    d['premierLeagueTable']=parse_table_tokens(tokens(PL_TABLE),'PremierLeague.com official')
    health['premierLeagueTable']='PremierLeague.com official'
  except Exception as e:
    print('PL table',e)
    try:
      d['premierLeagueTable']=parse_table_tokens(tokens(BBC_TABLE),'BBC Sport UK fallback')
      health['premierLeagueTable']='BBC Sport UK fallback'
    except Exception as be:
      print('BBC table',be);health['premierLeagueTable']='preserved last-known-good table'
  n=news()
  if n:d['news']=n
  d['dataSources']={'fixtures':'LOCKED verified Liverpool FC schedule','premierLeagueTable':'PremierLeague.com official → BBC Sport UK fallback','broadcastUS':'confirmed match-specific listings where available'}
  d['dataHealth']=health
  d['updated']=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
  DATA.write_text(json.dumps(d,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
