"""验证水车分配方案的可比性、容量约束、脆弱性与复算解释。"""
import json,unittest
from pathlib import Path
from climate_analysis.evidence import connect,receive,save_plan,get_plan
from climate_analysis.allocation import assess,explain
DATA=json.loads((Path(__file__).resolve().parents[1]/'data/allocation_example.json').read_text(encoding='utf8'))
class Allocation(unittest.TestCase):
 def setUp(self):
  self.db=connect(':memory:')
  for doc in DATA['documents']:receive(self.db,doc)
 def tearDown(self):self.db.close()
 def _by_region(self,plan):return {e['region']:e for e in plan['regions']}
 def test_capacity_and_vulnerability(self):
  plan=assess(self.db,DATA['known_at'][0]);by=self._by_region(plan)
  self.assertEqual(plan['totals']['trucks_used'],plan['fleet']['trucks'])
  self.assertLessEqual(plan['totals']['aid'],plan['fleet']['total_capacity'])
  # 异常比例最低(0.30)但人口暴露最大的 region-B 拿到最多水车，而不是按比例最高的 region-C(0.55)
  self.assertEqual(by['region-B']['trucks_allocated'],10)
  self.assertGreater(by['region-B']['trucks_allocated'],by['region-C']['trucks_allocated'])
  self.assertAlmostEqual(plan['totals']['unmet'],plan['totals']['net_need']-plan['totals']['aid'])
 def test_comparability_limitations(self):
  plan=assess(self.db,DATA['known_at'][0]);by=self._by_region(plan)
  self.assertFalse(plan['comparability']['rankable'])
  self.assertTrue(any('基线口径不一致' in s for s in plan['comparability']['limitations']))
  self.assertTrue(any('region-D' in s for s in plan['comparability']['limitations']))
  for e in by.values():self.assertIsNone(e['rank'])
  self.assertEqual(by['region-B']['rank_in_group'],1)
  self.assertEqual(by['region-A']['rank_in_group'],2)
  self.assertEqual(by['region-C']['rank_in_group'],1)
  self.assertTrue(by['region-D']['notes'])
 def test_recompute_explains_change(self):
  a,b=[assess(self.db,t) for t in DATA['known_at']]
  fa=save_plan(self.db,a,approved_at=a['known_at']);save_plan(self.db,b,approved_at=b['known_at'])
  change=explain(a,b);after=self._by_region(b)
  self.assertEqual(after['region-C']['alternative_supply'],700)
  c=change['regions']['region-C']
  self.assertEqual((c['trucks_before'],c['trucks_after']),(4,2))
  self.assertLess(c['aid_after'],c['aid_before']);self.assertLess(c['unmet_after'],c['unmet_before'])
  self.assertEqual(change['regions']['region-B']['trucks_after'],11)
  self.assertLess(change['totals']['unmet_after'],change['totals']['unmet_before'])
  self.assertTrue(any('region-C' in s and '替代供水' in s for s in change['explanation']))
  self.assertTrue(any('未满足需求' in s for s in change['explanation']))
 def test_approved_plan_basis_queryable(self):
  a=assess(self.db,DATA['known_at'][0]);fa=save_plan(self.db,a,approved_at=a['known_at'])
  assess(self.db,DATA['known_at'][1])
  saved=get_plan(self.db,fa)
  self.assertEqual(saved['fingerprint'],fa)
  self.assertTrue(all(e['sources'] for e in saved['regions']))
  self.assertTrue(saved['fleet']['sources'] and saved['parameters']['sources'])
  self.assertEqual(assess(self.db,DATA['known_at'][0])['fingerprint'],fa)
if __name__=='__main__':unittest.main()
