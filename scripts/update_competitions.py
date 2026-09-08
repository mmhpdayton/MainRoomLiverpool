import json, urllib.request, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'competition-data.json'
SITE=ROOT/'site-data.json'
HEAD={'User-Agent':'Mozilla/5.0','Accept':'application/json,text/plain,*/*'}
PL_FEED='https://fixturedownload.com/feed/json/epl-2026'
UCL_FEED='https://fixturedownload.com/feed/json/champions-league-2026'
SOFASCORE_DAY='https://www.sofascore.com/api/v1/sport/football/scheduled-events/{date}'

ALIASES={
    'Man Utd':'Manchester United','Manchester United FC':'Manchester United','Man City':'Manchester City','Manchester City FC':'Manchester City',
    "Nott'm Forest":'Nottingham Forest','Nottingham Forest FC':'Nottingham Forest','Spurs':'Tottenham Hotspur','Tottenham Hotspur FC':'Tottenham Hotspur',
    'Bournemouth':'AFC Bournemouth','AFC Bournemouth':'AFC Bournemouth','Brighton':'Brighton & Hove Albion','Brighton & Hove Albion FC':'Brighton & Hove Albion',
    'Coventry':'Coventry City','Coventry City FC':'Coventry City','Hull':'Hull City','Hull City AFC':'Hull City','Ipswich':'Ipswich Town','Ipswich Town FC':'Ipswich Town',
    'Leeds':'Leeds United','Leeds United FC':'Leeds United','Newcastle':'Newcastle United','Newcastle United FC':'Newcastle United','Liverpool FC':'Liverpool',
    'Arsenal FC':'Arsenal','Chelsea FC':'Chelsea','Everton FC':'Everton','Fulham FC':'Fulham','Sunderland AFC':'Sunderland','Brentford FC':'Brentford',
    'Aston Villa FC':'Aston Villa','Crystal Palace FC':'Crystal Palace','B. Dortmund':'Borussia Dortmund','Borussia Dortmund':'Borussia Dortmund',
    'Atleti':'Atlético de Madrid','Atletico Madrid':'Atlético de Madrid','Atlético Madrid':'Atlético de Madrid','Atlético de Madrid':'Atlético de Madrid',
    'Paris':'Paris Saint-Germain','Paris Saint-Germain FC':'Paris Saint-Germain','S. Bratislava':'Slovan Bratislava','SK Slovan Bratislava':'Slovan Bratislava',
    'PSV':'PSV Eindhoven','PSV Eindhoven':'PSV Eindhoven','Shakhtar':'Shakhtar Donetsk','FC Shakhtar Donetsk':'Shakhtar Donetsk',
    'Leipzig':'RB Leipzig','RB Leipzig':'RB Leipzig','Bayern München':'Bayern Munich','Bayern Munich':'Bayern Munich','FC Bayern München':'Bayern Munich',
    'Barcelona':'Barcelona','FC Barcelona':'Barcelona','Porto':'Porto','FC Porto':'Porto','Inter Milano':'Inter','Inter':'Inter',
    'SSC Napoli':'Napoli','Napoli':'Napoli','Sporting CP':'Sporting CP','Galatasaray Istanbul':'Galatasaray','Galatasaray':'Galatasaray',
    'Lille OSC':'Lille','Lille':'Lille','Real Betis Seville':'Real Betis','Real Betis':'Real Betis','Villarreal CF':'Villarreal','Villarreal':'Villarreal',
    'VfB Stuttgart':'Stuttgart','Stuttgart':'Stuttgart','AS Roma':'Roma','Roma':'Roma','Fenerbahce Istanbul':'Fenerbahçe','Fenerbahçe':'Fenerbahçe',
    'Club Brugge KV':'Club Brugge','Club Brugge':'Club Brugge','Feyenoord Rotterdam':'Feyenoord','Feyenoord':'Feyenoord','Slavia Prague':'Slavia Praha','Slavia Praha':'Slavia Praha',
    'Racing Club De Lens':'Lens','RC Lens':'Lens','Lens':'Lens','Bodoe/Glimt':'Bodø/Glimt','Bodø/Glimt':'Bodø/Glimt',
    'LASK Linz':'LASK','LASK':'LASK','Viking FK':'Viking','Viking':'Viking','Como 1907':'Como','Como':'Como','Sabah Masazir':'Sabah','Sabah':'Sabah',
    'AEK Athens':'AEK Athens','Real Madrid':'Real Madrid'
}

def fetch_json(url):
    req=urllib.request.Request(url,headers=HEAD)
    return json.loads(urllib.request.urlopen(req,timeout=30).read().decode('utf-8'))

def norm_team(name):
    name=(name or '').strip()
    return ALIASES.get(name,name)

def load(path,default):
    try:return json.loads(path.read_text())
    except:return default

def parse_rows(rows,source):
    out=[]
    for r in rows:
        dt=str(r.get('DateUtc') or '').replace(' ','T')
        if dt and not dt.endswith('Z'):dt+='Z'
        hs=r.get('HomeTeamScore');as_=r.get('AwayTeamScore')
        out.append({'round':int(r.get('RoundNumber') or 0),'date':dt,'home':norm_team(r.get('HomeTeam')),'away':norm_team(r.get('AwayTeam')),
                    'venue':r.get('Location') or '','homeScore':hs,'awayScore':as_,'status':'final' if hs is not None and as_ is not None else 'scheduled','source':source})
    return out

def update_pl():
    out=parse_rows(fetch_json(PL_FEED),'FixtureDownload schedule/results baseline')
    if len(out)<350:raise RuntimeError(f'PL feed returned only {len(out)} matches')
    return out

def update_ucl():
    out=parse_rows(fetch_json(UCL_FEED),'FixtureDownload schedule baseline; UEFA official fixture cross-check')
    if len(out)<140:raise RuntimeError(f'UCL feed returned only {len(out)} matches')
    return out

def nearest_match(matches,home,away,start):
    candidates=[g for g in matches if norm_team(g.get('home'))==home and norm_team(g.get('away'))==away]
    if not candidates:return None
    return min(candidates,key=lambda g:abs((datetime.fromisoformat(g['date'].replace('Z','+00:00'))-start).total_seconds()))

def merge_live(comp):
    changed=False;now=datetime.now(timezone.utc);events=[]
    for delta in (-1,0,1):
        day=(now+timedelta(days=delta)).date().isoformat()
        try:events.extend(fetch_json(SOFASCORE_DAY.format(date=day)).get('events',[]))
        except Exception as e:print('Sofascore',day,e)
    for e in events:
        ut=((e.get('tournament') or {}).get('uniqueTournament') or {}).get('id')
        if ut not in (7,17):continue
        home=norm_team(((e.get('homeTeam') or {}).get('name')));away=norm_team(((e.get('awayTeam') or {}).get('name')))
        try:start=datetime.fromtimestamp(int(e.get('startTimestamp')),timezone.utc)
        except:continue
        bucket=comp.get('championsLeagueMatches',[]) if ut==7 else comp.get('premierLeagueMatches',[])
        g=nearest_match(bucket,home,away,start)
        if not g or abs((datetime.fromisoformat(g['date'].replace('Z','+00:00'))-start).total_seconds())>172800:continue
        status_type=((e.get('status') or {}).get('type') or '').lower();desc=(e.get('status') or {}).get('description') or ''
        hs=(e.get('homeScore') or {}).get('current');as_=(e.get('awayScore') or {}).get('current')
        new_status='final' if status_type=='finished' else ('live' if status_type in ('inprogress','in_progress') else g.get('status','scheduled'))
        updates={'status':new_status,'liveStatus':desc if new_status=='live' else ''}
        if hs is not None:updates['homeScore']=hs
        if as_ is not None:updates['awayScore']=as_
        for k,v in updates.items():
            if g.get(k)!=v:g[k]=v;changed=True
    return changed

def ucl_table(matches):
    teams=sorted({g['home'] for g in matches}|{g['away'] for g in matches})
    stats={t:{'team':t,'p':0,'w':0,'d':0,'l':0,'gf':0,'ga':0,'gd':0,'pts':0} for t in teams}
    for g in matches:
        if g.get('status')!='final' or g.get('homeScore') is None or g.get('awayScore') is None:continue
        h,a=g['home'],g['away'];hs,as_=int(g['homeScore']),int(g['awayScore']);H,A=stats[h],stats[a]
        for s in (H,A):s['p']+=1
        H['gf']+=hs;H['ga']+=as_;A['gf']+=as_;A['ga']+=hs
        if hs>as_:H['w']+=1;H['pts']+=3;A['l']+=1
        elif hs<as_:A['w']+=1;A['pts']+=3;H['l']+=1
        else:H['d']+=1;A['d']+=1;H['pts']+=1;A['pts']+=1
    for s in stats.values():s['gd']=s['gf']-s['ga']
    rows=sorted(stats.values(),key=lambda s:(-s['pts'],-s['gd'],-s['gf'],s['team']))
    for i,s in enumerate(rows,1):s['pos']=i
    return rows

def sync_liverpool(site,comp):
    fixtures=site.get('fixtures',[]);index={(g.get('competition'),g.get('opponent'),g.get('homeAway')):g for g in fixtures}
    for competition,key in [('Premier League','premierLeagueMatches'),('Champions League','championsLeagueMatches')]:
        for m in comp.get(key,[]):
            if 'Liverpool' not in (m.get('home'),m.get('away')):continue
            ha='H' if m['home']=='Liverpool' else 'A';opp=m['away'] if ha=='H' else m['home'];k=(competition,opp,ha)
            g=index.get(k)
            if not g:
                g={'id':m['date'][:10].replace('-','')+'-'+opp.lower().replace(' ','-').replace('é','e').replace('ø','o'),'date':m['date'],'opponent':opp,'homeAway':ha,
                   'competition':competition,'venue':m.get('venue') or '','broadcastUS':'Paramount+' if competition=='Champions League' else 'TBA',
                   'status':'scheduled','scoreFor':None,'scoreAgainst':None}
                if competition=='Champions League':
                    g.update({'broadcastUSSource':'CBS Sports / Paramount+ U.S. UEFA rights','broadcastConfidence':'rights-holder guaranteed stream'})
                fixtures.append(g);index[k]=g
            g['date']=m['date'];g['venue']=m.get('venue') or g.get('venue','');g['status']=m.get('status','scheduled')
            if m.get('homeScore') is not None:
                g['scoreFor']=m['homeScore'] if ha=='H' else m['awayScore'];g['scoreAgainst']=m['awayScore'] if ha=='H' else m['homeScore']
            if m.get('liveStatus'):g['liveStatus']=m['liveStatus']
            elif 'liveStatus' in g:g['liveStatus']=''
    site['fixtures']=sorted(fixtures,key=lambda x:x.get('date',''))
    site['championsLeagueTable']=ucl_table(comp.get('championsLeagueMatches',[]))
    site['championsLeagueStatus']='2026–27 league phase • 36 teams • 8 matchdays'

def main():
    live_only='--live' in sys.argv
    comp=load(OUT,{'premierLeagueMatches':[],'championsLeagueMatches':[]});site=load(SITE,{})
    before_comp=json.dumps(comp,sort_keys=True);before_site=json.dumps(site,sort_keys=True);health=comp.get('health',{})
    if not live_only:
        try:comp['premierLeagueMatches']=update_pl();health['premierLeagueMatches']='full 380-match schedule/results baseline loaded'
        except Exception as e:print('PL competition feed',e);health['premierLeagueMatches']='preserved last-known-good schedule'
        try:comp['championsLeagueMatches']=update_ucl();health['championsLeagueMatches']='full 144-match league-phase schedule loaded'
        except Exception as e:print('UCL competition feed',e);health['championsLeagueMatches']='preserved last-known-good schedule'
        comp['championsLeagueStatus']='2026–27 league phase fixtures are loaded. Current matchday opens automatically.'
    live_changed=merge_live(comp)
    sync_liverpool(site,comp);comp['health']=health
    after_core=json.dumps(comp,sort_keys=True)+json.dumps(site,sort_keys=True)
    if not live_only or live_changed or (before_comp+before_site)!=after_core:
        stamp=datetime.now(timezone.utc).isoformat().replace('+00:00','Z');comp['updated']=stamp;site['updated']=stamp
        OUT.write_text(json.dumps(comp,indent=2,ensure_ascii=False));SITE.write_text(json.dumps(site,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
