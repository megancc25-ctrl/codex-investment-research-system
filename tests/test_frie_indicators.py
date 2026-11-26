import unittest
from market_risk.frie import indicators as i
from market_risk.frie import backtest as b

class IndicatorTests(unittest.TestCase):
    def test_missing_and_finite(self):
        self.assertEqual(i.f03_crowding(None)['status'],'UNKNOWN')
        with self.assertRaises(ValueError): i.f03_crowding(float('nan'))
        with self.assertRaises(ValueError): i.f03_crowding(101)
    def test_thresholds(self):
        self.assertEqual(i.f03_crowding(90)['status'],'TRIGGERED')
        self.assertEqual(i.f04_volatility_leverage(19,91)['status'],'TRIGGERED')
        self.assertEqual(i.f04_volatility_leverage(20,91)['status'],'NOT_TRIGGERED')
        self.assertEqual(i.f02_valuation_growth(95,2,valuation_threshold=90,growth_excess_threshold=1)['status'],'TRIGGERED')
    def test_paired_fcf(self):
        vendors={'a':{'current':[(10,4),(10,5)],'prior_year':[(12,3),(12,3)]},
                 'b':{'current':[(10,4),(10,5)],'prior_year':[(12,3),(12,3)]}}
        self.assertEqual(i.f06_fcf_declines(vendors)['status'],'TRIGGERED')
        self.assertEqual(i.f06_fcf_declines({'a':vendors['a']})['status'],'UNKNOWN')
    def test_capex_and_oas(self):
        self.assertEqual(i.f07_capex_debt([10,10],[2,3],[1,2])['status'],'TRIGGERED')
        self.assertEqual(i.f07_capex_debt([0,10],[2,3],[1,2])['status'],'UNKNOWN')
        self.assertEqual(i.f08_hy_oas([300]*20+[400],unit='bp')['status'],'TRIGGERED')
        with self.assertRaises(ValueError): i.f08_hy_oas([4],unit='percent')
    def test_vix_breadth_and_relative(self):
        self.assertEqual(i.f15_vix_term([22,24],[20,20],ratio_threshold=1,persistence=2)['status'],'TRIGGERED')
        self.assertEqual(i.f18_breadth({'advance':20,'above_ma':30},thresholds={'advance':25,'above_ma':35})['status'],'TRIGGERED')
        self.assertEqual(i.o09_relative_strength(list(range(1,221)),earnings_support=True)['status'],'TRIGGERED')
        self.assertEqual(i.o09_relative_strength(list(range(1,221)),earnings_support=None)['status'],'UNKNOWN')
    def test_three_way_no_overlap(self):
        train,validation,test=b.purged_three_way_split(300,100,200,20)
        self.assertEqual((train[-1],validation[0],validation[-1],test[0]),(79,100,179,200))
