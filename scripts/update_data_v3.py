from update_data_v2 import *

def date_markers(fixture):
  d=datetime.fromisoformat(fixture['date'].replace('Z','+00:00')).astimezone(ZoneInfo('America/New_York'))
  return [f'{d.strftime("%b")}. {d.day}'.lower(),f'{d.strftime("%b")} {d.day}'.lower(),f'{d.strftime("%B")} {d.day}'.lower()]

def opp_variants(name):
  vals={name,name.replace('AFC ',''),name.replace(' & Hove Albion',''),name.replace(' United',''),name.replace(' City',''),name.replace(' Town','')}
  for a,b in ALIASES.items():
    if b==name:vals.add(a)
  return [v.lower() for v in vals if len(v)>=4]

def exact_outlets(tokens,fixture,allowed,require_date=True):
  markers=date_markers(fixture);ov=opp_variants(fixture['opponent']);hits=[]
  for i,s in enumerate(tokens):
    low=s.lower()
    same_token='liverpool' in low and any(v in low for v in ov)
    small=' | '.join(tokens[max(0,i-3):i+4]).lower()
    split_row=('liverpool' in small and any(v in small for v in ov))
    if not (same_token or split_row):continue
    context=' | '.join(tokens[max(0,i-8):i+8]).lower()
    if require_date and not any(m in context for m in markers):continue
    hits.append(i)
  found=[]
  for i in hits:
    # Platform is normally in the same cell or immediately after the match cell.
    context=' | '.join(tokens[max(0,i-2):i+6])
    for name in allowed:
      if name.lower() in context.lower() and name not in found:found.append(name)
  return found

def preload_broadcast_sources():
  src={'nbc_pages':[],'ucl':[],'carabao':[],'fa':[]}
  try:
    hub=page(NBC_PL_HUB);urls=[]
    for h in hub.links:
      if '/pressbox/press-releases/' in h:
        u=urllib.parse.urljoin(NBC_PL_HUB,h)
        if u not in urls:urls.append(u)
    for u in urls[:10]:
      try:src['nbc_pages'].append((u,page(u).tokens))
      except Exception:pass
  except Exception:pass
  for key,url in [('ucl',CBS_UCL),('carabao',CBS_CARABAO),('fa',ESPN_FA)]:
    try:src[key]=page(url).tokens
    except Exception:src[key]=[]
  return src

def refresh_broadcasts(fixtures):
  src=preload_broadcast_sources();now=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
  for x in fixtures:
    comp=x.get('competition');found=[];source=''
    # Never carry forward an outlet unless it is reconfirmed by the current official scan.
    x['broadcastUS']='TBA';x['broadcastUSSource']='';x['broadcastConfidence']='';x['broadcastCheckedAt']=now
    if comp=='Premier League':
      for u,t in src['nbc_pages']:
        found=exact_outlets(t,x,['USA Network','Peacock','NBCSN','NBC','CNBC','SYFY'])
        if found:source=u;break
    elif comp=='Champions League':
      found=exact_outlets(src['ucl'],x,['CBS Sports Network','CBS Sports Golazo Network','CBS','Paramount+'])
      if 'Paramount+' not in found:found=['Paramount+']+found
      source=CBS_UCL if len(found)>1 else 'Paramount Press Express — every UEFA match streams on Paramount+'
    elif comp=='Carabao Cup':
      found=exact_outlets(src['carabao'],x,['CBS Sports Network','CBS Sports Golazo Network','CBS','Paramount+'])
      if found:source=CBS_CARABAO
    elif comp=='FA Cup':
      found=exact_outlets(src['fa'],x,['ESPN2','ESPN+','ESPN Deportes','ESPN'])
      if found:source=ESPN_FA
    if found:
      x['broadcastUS']=' • '.join(dict.fromkeys(found));x['broadcastUSSource']=source;x['broadcastConfidence']='official match-specific' if source.startswith('http') else 'official rights baseline'
  return fixtures

def main():
  d=json.loads(DATA.read_text());health={}
  try:d['fixtures'],health['fixtures']=guarded_fixture_refresh(d.get('fixtures',[]))
  except Exception as e:print('fixtures',e);health['fixtures']='preserved last-known-good schedule'
  try:d['fixtures']=refresh_broadcasts(d.get('fixtures',[]));health['broadcastUS']='exact-row/date official scan completed'
  except Exception as e:print('broadcasts',e);health['broadcastUS']='broadcast refresh failed; review required'
  try:d['premierLeagueTable']=parse_table_tokens(page(PL_TABLE).tokens,'PremierLeague.com official');health['premierLeagueTable']='PremierLeague.com official'
  except Exception as e:
    print('PL table',e)
    try:d['premierLeagueTable']=parse_table_tokens(page(BBC_TABLE).tokens,'BBC Sport UK fallback');health['premierLeagueTable']='BBC Sport UK fallback'
    except Exception as be:print('BBC table',be);health['premierLeagueTable']='preserved last-known-good table'
  n=news()
  if n:d['news']=n
  d['dataSources']={'fixtures':'Liverpool FC official; PL identity protected; named UCL/FA/Carabao fixtures added automatically','premierLeagueTable':'PremierLeague.com official → BBC Sport fallback','broadcastUS':'Exact match row + exact date required from NBC Sports / CBS Sports / ESPN; Paramount+ guaranteed baseline for UCL'}
  d['dataHealth']=health;d['updated']=datetime.now(timezone.utc).isoformat().replace('+00:00','Z');DATA.write_text(json.dumps(d,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
