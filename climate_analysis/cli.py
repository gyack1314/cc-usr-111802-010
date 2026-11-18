"""从本地合成资料形成两个已知时间的报告。"""
import argparse,json
from pathlib import Path
from .evidence import connect,receive,save_plan
from .report import generate,difference
from .allocation import assess,explain
def main():
 p=argparse.ArgumentParser();p.add_argument('command',choices=['inspect','allocate']);p.add_argument('input')
 p.add_argument('--db',default=':memory:');args=p.parse_args()
 data=json.loads(Path(args.input).read_text(encoding='utf8'));db=connect(args.db)
 for doc in data['documents']:receive(db,doc)
 if args.command=='inspect':
  a,b=[generate(db,t) for t in data['known_at']]
  print(json.dumps({'before':a,'after':b,'change':difference(a,b)},ensure_ascii=False,indent=2))
 else:
  plans=[assess(db,t) for t in data['known_at']]
  for t,plan in zip(data['known_at'],plans):save_plan(db,plan,approved_at=t)
  out={'plans':plans}
  if len(plans)==2:out['change']=explain(plans[0],plans[1])
  print(json.dumps(out,ensure_ascii=False,indent=2))
 db.close()
if __name__=='__main__':main()
