from update_data_v5 import *

CONFIRMED_FIXTURE_CHANGES={
  ('Premier League','Manchester City','H'):{'date':'2026-10-11T15:30:00Z','source':'Premier League fixture amendment — 2026-08-17','broadcastUK':'Sky Sports'},
  ('Premier League','Arsenal','H'):{'date':'2026-11-01T16:30:00Z','source':'Premier League fixture amendment — 2026-08-17','broadcastUK':'Sky Sports'}
}

KNOWN_CUP_FIXTURES=[
  {
    'id':'20260915-tottenham-hotspur-carabao','date':'2026-09-15T19:00:00Z','opponent':'Tottenham Hotspur','homeAway':'H','competition':'Carabao Cup','venue':'Anfield',
    'broadcastUS':'Paramount+','broadcastUSSource':'https://www.cbssports.com/soccer/carabao-cup/schedule/','broadcastConfidence':'official broadcaster match-specific',
    'status':'scheduled','scoreFor':None,'scoreAgainst':None,'fixtureSource':'Liverpool FC official — fixture moved to 15 September 2026'
  }
]

KNOWN_SPANISH={
  ('Champions League','Atlético de Madrid','H','2026-09-09'):{'outlets':['UniMás','TUDN','ViX'],'source':'https://www.tudn.com/futbol/partidos-hoy-miercoles-9-septiembre-2026-mexicanos-en-el-exterior-y-champions-league'}
}

def cup_key(x):return (x.get('competition'),x.get('opponent'),x.get('homeAway'))

def apply_known_cup_fixtures(fixtures):
  """Add known cup ties and restore confirmed metadata after generic scanners run."""
  out=list(fixtures)
  for known in KNOWN_CUP_FIXTURES:
    existing=next((x for x in out if cup_key(x)==cup_key(known)),None)
    if existing:
      for k in ('date','venue','fixtureSource','broadcastUS','broadcastUSSource','broadcastConfidence'):
        if known.get(k) is not None:existing[k]=known[k]
    else:out.append(dict(known))
  return sorted(out,key=lambda x:x['date'])

def guarded_fixture_refresh(old):
  try:fresh=parse_lfc_fixtures()
  except Exception as e:print('Liverpool FC fixture parse',e);fresh=[]
  fresh_by_key={(x.get('competition'),x.get('opponent'),x.get('homeAway')):x for x in fresh if x.get('opponent') not in ('TBC','TBA','')}
  final=[];seen=set()
  for prior in old:
    key=cup_key(prior);current=dict(prior);official=fresh_by_key.get(key)
    if official:
      if prior.get('competition')=='Premier League':
        current['date']=official.get('date') or current.get('date')
        if official.get('venue'):current['venue']=official['venue']
        current['fixtureSource']='Liverpool FC official'
      else:
        for k in ('date','venue','status','scoreFor','scoreAgainst'):
          if official.get(k) is not None:current[k]=official[k]
        current['fixtureSource']='Liverpool FC official'
    final.append(current);seen.add(key)
  for key,x in fresh_by_key.items():
    if key in seen or x.get('competition')=='Premier League':continue
    final.append(x);seen.add(key)
  final=apply_known_cup_fixtures(final)
  for x in final:
    change=CONFIRMED_FIXTURE_CHANGES.get(cup_key(x))
    if change:
      x['date']=change['date'];x['fixtureChangeSource']=change['source']
      if change.get('broadcastUK'):x['broadcastUK']=change['broadcastUK']
  return sorted(final,key=lambda x:x['date']),'Liverpool FC official per-fixture merge + confirmed amendment/cup safety net'

def refresh_spanish_broadcasts(fixtures):
  src=preload_broadcast_sources();now=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
  for x in fixtures:
    dt=datetime.fromisoformat(x['date'].replace('Z','+00:00')).astimezone(ZoneInfo('Europe/London'))
    key=(x.get('competition'),x.get('opponent'),x.get('homeAway'),dt.date().isoformat());found=[];source=''
    x['broadcastUSSpanish']='TBA';x['broadcastUSSpanishSource']='';x['broadcastUSSpanishConfidence']='';x['broadcastUSSpanishCheckedAt']=now
    if key in KNOWN_SPANISH:found=KNOWN_SPANISH[key]['outlets'];source=KNOWN_SPANISH[key]['source']
    elif x.get('competition')=='Premier League':
      for u,rows in src['nbc_pages']:
        found=row_outlets(rows,x,['Telemundo','Universo'])
        if found:source=u;break
    elif x.get('competition')=='FA Cup' and 'ESPN Deportes' in (x.get('broadcastUS') or ''):
      found=['ESPN Deportes'];source=x.get('broadcastUSSource') or ESPN_FA
      english=[v.strip() for v in (x.get('broadcastUS') or '').split('•') if v.strip() and v.strip()!='ESPN Deportes']
      x['broadcastUS']=' • '.join(english) if english else 'TBA'
    if found:x['broadcastUSSpanish']=' • '.join(dict.fromkeys(found));x['broadcastUSSpanishSource']=source;x['broadcastUSSpanishConfidence']='official match-specific'
  return fixtures

def main():
  d=json.loads(DATA.read_text());health={}
  try:d['fixtures'],health['fixtures']=guarded_fixture_refresh(d.get('fixtures',[]))
  except Exception as e:print('fixtures',e);health['fixtures']='preserved last-known-good schedule'
  try:d['fixtures']=refresh_broadcasts(d.get('fixtures',[]));d['fixtures']=apply_known_cup_fixtures(d['fixtures']);health['broadcastUS']='official broadcaster scan + confirmed cup broadcast safety net'
  except Exception as e:print('broadcasts',e);health['broadcastUS']='broadcast refresh failed; review required'
  try:d['fixtures']=refresh_spanish_broadcasts(d.get('fixtures',[]));health['broadcastUSSpanish']='official match-specific Spanish-language scan completed'
  except Exception as e:print('Spanish broadcasts',e);health['broadcastUSSpanish']='Spanish broadcast refresh failed; last-known-good data may remain'
  try:d['premierLeagueTable']=parse_table_tokens(page(PL_TABLE).tokens,'PremierLeague.com official');health['premierLeagueTable']='PremierLeague.com official'
  except Exception as e:
    print('PL table',e)
    try:d['premierLeagueTable']=parse_table_tokens(page(BBC_TABLE).tokens,'BBC Sport UK fallback');health['premierLeagueTable']='BBC Sport UK fallback'
    except Exception as be:print('BBC table',be);health['premierLeagueTable']='preserved last-known-good table'
  n=news()
  if n:d['news']=n
  d['dataSources']={'fixtures':'Liverpool FC official per-fixture merge; PL identity protected; confirmed amendments safety-net; named UCL/FA/Carabao fixtures added automatically; confirmed cup ties have additive safety nets','premierLeagueTable':'PremierLeague.com official → BBC Sport fallback','broadcastUS':'Official broadcaster scan plus persistent match-specific cup safety nets; Paramount+ guaranteed baseline for UCL','broadcastUSSpanish':'Separate exact-match Spanish-language field; NBC/Telemundo official rows for PL; TUDN match-specific listings for UCL; TBA rather than guessing'}
  d['dataHealth']=health;d['updated']=datetime.now(timezone.utc).isoformat().replace('+00:00','Z');DATA.write_text(json.dumps(d,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
