from update_data_v4 import *

class TableParser(HTMLParser):
  def __init__(self):super().__init__();self.rows=[];self.row=None;self.cell=None;self.skip=0
  def handle_starttag(self,tag,attrs):
    if tag in ('script','style','noscript'):self.skip+=1
    if tag=='tr':self.row=[]
    elif tag in ('td','th') and self.row is not None:self.cell=[]
  def handle_endtag(self,tag):
    if tag in ('script','style','noscript') and self.skip:self.skip-=1
    elif tag in ('td','th') and self.cell is not None:
      self.row.append(' '.join(self.cell));self.cell=None
    elif tag=='tr' and self.row is not None:
      if self.row:self.rows.append(self.row)
      self.row=None
  def handle_data(self,data):
    if not self.skip and self.cell is not None:
      s=' '.join(html.unescape(data).split())
      if s:self.cell.append(s)

def table_rows(url):
  p=TableParser();p.feed(request(url).decode('utf-8','ignore'));return p.rows

def row_outlets(rows,fixture,allowed):
  markers=date_markers(fixture);ov=opp_variants(fixture['opponent']);found=[]
  for row in rows:
    text=' | '.join(row);low=text.lower()
    if 'liverpool' not in low or not any(v in low for v in ov):continue
    if not any(m in low for m in markers):continue
    for name in allowed:
      if name.lower() in low and name not in found:found.append(name)
    if found:return found
  return found

def preload_broadcast_sources():
  src={'nbc_pages':[],'ucl_rows':[],'carabao_rows':[],'fa_rows':[],'ucl_tokens':[],'carabao_tokens':[],'fa_tokens':[]}
  try:
    hub=page(NBC_PL_HUB);urls=[]
    for h in hub.links:
      if '/pressbox/press-releases/' in h:
        u=urllib.parse.urljoin(NBC_PL_HUB,h)
        if u not in urls:urls.append(u)
    for u in urls[:10]:
      try:src['nbc_pages'].append((u,table_rows(u)))
      except Exception:pass
  except Exception:pass
  for key,url in [('ucl',CBS_UCL),('carabao',CBS_CARABAO),('fa',ESPN_FA)]:
    try:src[key+'_rows']=table_rows(url)
    except Exception:pass
    try:src[key+'_tokens']=page(url).tokens
    except Exception:pass
  return src

KNOWN={
 ('Premier League','Newcastle United','A','2026-08-23'):{'outlets':['USA Network'],'source':'https://www.nbcsports.com/pressbox/press-releases/the-2026-27-premier-league-season-kicks-off-in-one-month-across-platforms-of-nbcuniversal-with-nbc-sports-studio-team-on-site-in-u-k'}
}

def refresh_broadcasts(fixtures):
  src=preload_broadcast_sources();now=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
  for x in fixtures:
    dt=datetime.fromisoformat(x['date'].replace('Z','+00:00')).astimezone(ZoneInfo('Europe/London'));key=(x.get('competition'),x.get('opponent'),x.get('homeAway'),dt.date().isoformat());found=[];source=''
    x['broadcastUS']='TBA';x['broadcastUSSource']='';x['broadcastConfidence']='';x['broadcastCheckedAt']=now
    if key in KNOWN:found=KNOWN[key]['outlets'];source=KNOWN[key]['source']
    elif x.get('competition')=='Premier League':
      for u,rows in src['nbc_pages']:
        found=row_outlets(rows,x,['USA Network','Peacock','NBCSN','NBC','CNBC','SYFY'])
        if found:source=u;break
    elif x.get('competition')=='Champions League':
      found=row_outlets(src['ucl_rows'],x,['CBS Sports Network','CBS Sports Golazo Network','CBS','Paramount+']) or exact_outlets(src['ucl_tokens'],x,['CBS Sports Network','CBS Sports Golazo Network','CBS','Paramount+'])
      if 'Paramount+' not in found:found=['Paramount+']+found
      source=CBS_UCL if len(found)>1 else 'Paramount Press Express — every UEFA match streams on Paramount+'
    elif x.get('competition')=='Carabao Cup':
      found=row_outlets(src['carabao_rows'],x,['CBS Sports Network','CBS Sports Golazo Network','CBS','Paramount+']) or exact_outlets(src['carabao_tokens'],x,['CBS Sports Network','CBS Sports Golazo Network','CBS','Paramount+'])
      if found:source=CBS_CARABAO
    elif x.get('competition')=='FA Cup':
      found=row_outlets(src['fa_rows'],x,['ESPN2','ESPN+','ESPN Deportes','ESPN']) or exact_outlets(src['fa_tokens'],x,['ESPN2','ESPN+','ESPN Deportes','ESPN'])
      if found:source=ESPN_FA
    if found:
      x['broadcastUS']=' • '.join(dict.fromkeys(found));x['broadcastUSSource']=source;x['broadcastConfidence']='official match-specific' if source.startswith('http') else 'official rights baseline'
  return fixtures

if __name__=='__main__':main()
