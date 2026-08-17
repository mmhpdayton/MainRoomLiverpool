from update_data_v3 import *

def exact_outlets(tokens,fixture,allowed,require_date=True):
  markers=date_markers(fixture);ov=opp_variants(fixture['opponent']);same=[];split=[]
  for i,s in enumerate(tokens):
    low=s.lower();date_context=' | '.join(tokens[max(0,i-5):i+3]).lower()
    if require_date and not any(m in date_context for m in markers):continue
    if 'liverpool' in low and any(v in low for v in ov):same.append(i);continue
    small=' | '.join(tokens[max(0,i-2):i+3]).lower()
    if 'liverpool' in small and any(v in small for v in ov):split.append(i)
  hits=same or split;found=[]
  for i in hits:
    # For schedule tables, the outlet cell is the match token itself or the next one/two tokens.
    context=' | '.join(tokens[i:i+3]) if same else ' | '.join(tokens[max(0,i-1):i+3])
    for name in allowed:
      if name.lower() in context.lower() and name not in found:found.append(name)
  return found

if __name__=='__main__':main()
