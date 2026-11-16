import sys
sys.path.insert(0,'.'), sys.path.insert(0,'team/audit'), sys.path.insert(0,'research')
import pandas as pd
from inputs_k9 import K9Inputs
from fresh2_max import MaxInputs
piv=pd.read_pickle('data/pivots_2020_clean.pkl')
dates=piv['close'].index
grid=[d for i,d in enumerate(dates) if i>=300 and (i-300)%30==0]
print('use_max attr:', K9Inputs(piv,use_max=True,sel='amihud_5').use_max, K9Inputs(piv,use_max=False,sel='amihud_5').use_max)
for sel,leg,P in [('amihud_5','B',dict(band=(0.05,0.30),gate60=-1.0,max_cut=0.80,max_win=20))]:
  a=K9Inputs(piv,use_max=True,sel=sel,**P); b=K9Inputs(piv,use_max=False,sel=sel,**P)
  ndiff=0; ex=[]
  for t in grid:
    pa=a.picks(t,4,exclude=('688','689','300','301','8','4'),factor='amihud_60')
    pb=b.picks(t,4,exclude=('688','689','300','301','8','4'),factor='amihud_60')
    if pa!=pb:
      ndiff+=1
      if len(ex)<5: ex.append((str(t.date()),pa,pb))
  print(sel,leg,'grid n=',len(grid),'diff n=',ndiff,'examples=',ex)
import inspect
from design_r30_grid8 import X3Inputs
print(inspect.getsource(X3Inputs.picks))
