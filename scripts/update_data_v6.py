from update_data_v5 import *

# Confirmed fixture amendments. These are safety-net overrides sourced from official
# competition/club announcements, and are applied after the Liverpool FC page merge.
CONFIRMED_FIXTURE_CHANGES={
  ('Premier League','Manchester City','H'):{
    'date':'2026-10-11T15:30:00Z',
    'source':'Premier League fixture amendment — 2026-08-17',
    'broadcastUK':'Sky Sports'
  },
  ('Premier League','Arsenal','H'):{
    'date':'2026-11-01T16:30:00Z',
    'source':'Premier League fixture amendment — 2026-08-17',
    'broadcastUK':'Sky Sports'
  }
}

# Match-specific Spanish-language assignments that have been explicitly published by
# the U.S. Spanish-language rights holder. These are deliberately narrow: no guessing.
KNOWN_SPANISH={
  ('Champions League','Atlético de Madrid','H','2026-09-09'):{
    'outlets':['UniMás','TUDN','ViX'],
    'source':'https://www.tudn.com/futbol/partidos-hoy-miercoles-9-septiembre-2026-mexicanos-en-el-exterior-y-champions-league'
  }
}

def guarded_fixture_refresh(old):
  """Merge Liverpool FC's official fixture page match-by-match.

  PL opponent/home-away identity is never replaced wholesale. If Liverpool FC publishes
  a new date/time for the same exact PL fixture, that date is allowed through. Named
  UCL/FA Cup/Carabao Cup fixtures are additive and reconciled by identity.
  """
  try:fresh=parse_lfc_fixtures()
  except Exception as e:
    print('Liverpool FC fixture parse',e);fresh=[]

  fresh_by_key={(x.get('competition'),x.get('opponent'),x.get('homeAway')):x for x in fresh if x.get('opponent') not in ('TBC','TBA','')}
  final=[]
  seen=set()

  for prior in old:
    key=(prior.get('competition'),prior.get('opponent'),prior.get('homeAway'))
    current=dict(prior)
    official=fresh_by_key.get(key)
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

  for x in final:
    key=(x.get('competition'),x.get('opponent'),x.get('homeAway'))
    change=CONFIRMED_FIXTURE_CHANGES.get(key)
    if change:
      x['date']=change['date'];x['fixtureChangeSource']=change['source']
      if change.get('broadcastUK'):x['broadcastUK']=change['broadcastUK']

  return sorted(final,key=lambda x:x['date']),'Liverpool FC official per-fixture merge + confirmed amendment safety net'

def refresh_spanish_broadcasts(fixtures):
  """Add a separate U.S. Spanish-language outlet field using exact match listings only."""
  src=preload_broadcast_sources();now=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
  for x in fixtures:
    dt=datetime.fromisoformat(x['date'].replace('Z','+00:00')).astimezone(ZoneInfo('Europe/London'))
    key=(x.get('competition'),x.get('opponent'),x.get('homeAway'),dt.date().isoformat())
    found=[];source=''
    x['broadcastUSSpanish']='TBA';x['broadcastUSSpanishSource']='';x['broadcastUSSpanishConfidence']='';x['broadcastUSSpanishCheckedAt']=now
    if key in KNOWN_SPANISH:
      found=KNOWN_SPANISH[key]['outlets'];source=KNOWN_SPANISH[key]['source']
    elif x.get('competition')=='Premier League':
      for u,rows in src['nbc_pages']:
        found=row_outlets(rows,x,['Telemundo','Universo'])
        if found:source=u;break
    elif x.get('competition')=='FA Cup' and 'ESPN Deportes' in (x.get('broadcastUS') or ''):
      found=['ESPN Deportes'];source=x.get('broadcastUSSource') or ESPN_FA
      # Keep the English field clean when Deportes was captured by the legacy scanner.
      english=[v.strip() for v in (x.get('broadcastUS') or '').split('•') if v.strip() and v.strip()!='ESPN Deportes']
      x['broadcastUS']=' • '.join(english) if english else 'TBA'
    if found:
      x['broadcastUSSpanish']=' • '.join(dict.fromkeys(found));x['broadcastUSSpanishSource']=source;x['broadcastUSSpanishConfidence']='official match-specific'
  return fixtures

def main():
  d=json.loads(DATA.read_text());health={}
  try:d['fixtures'],health['fixtures']=guarded_fixture_refresh(d.get('fixtures',[]))
  except Exception as e:print('fixtures',e);health['fixtures']='preserved last-known-good schedule'
  try:d['fixtures']=refresh_broadcasts(d.get('fixtures',[]));health['broadcastUS']='official broadcaster table-row scan completed'
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
  d['dataSources']={'fixtures':'Liverpool FC official per-fixture merge; PL identity protected; confirmed amendments safety-net; named UCL/FA/Carabao fixtures added automatically','premierLeagueTable':'PremierLeague.com official → BBC Sport fallback','broadcastUS':'Same match + same date + same official broadcaster table row required; Paramount+ guaranteed baseline for UCL','broadcastUSSpanish':'Separate exact-match Spanish-language field; NBC/Telemundo official rows for PL; TUDN match-specific listings for UCL; TBA rather than guessing'}
  d['dataHealth']=health;d['updated']=datetime.now(timezone.utc).isoformat().replace('+00:00','Z');DATA.write_text(json.dumps(d,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
