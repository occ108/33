import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from maintenance import PlanConfig,build_maintenance_plan
from scripts.generate_synthetic import generate_synthetic
from streamlit.testing.v1 import AppTest
from pathlib import Path

class PlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=generate_synthetic().data
        cls.ref=cls.data.timestamp.max()
        cls.limits={('M-005','temperature_c'):82.,('M-005','vibration_mm_s'):3.8}

    def test_degradation_orders_review_before_early_band(self):
        original=self.data.copy(deep=True)
        plan=build_maintenance_plan(self.data,self.limits,self.ref)
        row=plan.loc[plan['Máquina'].eq('M-005')].iloc[0]
        self.assertEqual(row['Prioridad'],'Planificar revisión')
        self.assertLess(row['Revisar antes de (UTC)'],row['Banda inicial (UTC)'])
        self.assertGreater(row['Horas de uso hasta el umbral'],0)
        self.assertEqual(plan.iloc[0]['Máquina'],'M-005')
        pd.testing.assert_frame_equal(self.data,original)

    def test_old_data_do_not_get_current_deadlines(self):
        plan=build_maintenance_plan(self.data,self.limits,pd.Timestamp(int(self.ref.value)+10*24*3600*10**9,tz='UTC'))
        self.assertTrue(plan['Prioridad'].eq('Actualizar datos').all())
        self.assertTrue(plan['Revisar antes de (UTC)'].isna().all())

    def test_future_clock_and_short_series(self):
        plan=build_maintenance_plan(self.data,{},pd.Timestamp(int(self.ref.value)-24*3600*10**9,tz='UTC'))
        self.assertTrue(plan['Prioridad'].eq('Revisar fechas').all())
        small=self.data[self.data.asset_id.eq('M-001')].head(9)
        plan=build_maintenance_plan(small,{},small.timestamp.max())
        self.assertEqual(plan.iloc[0]['Prioridad'],'Datos insuficientes')

    def test_reached_limit_and_unconfigured(self):
        plan=build_maintenance_plan(self.data,{('M-005','temperature_c'):60},self.ref)
        self.assertEqual(plan.iloc[0]['Prioridad'],'Revisión prioritaria')
        self.assertEqual(plan.iloc[0]['Revisar antes de (UTC)'],self.ref)
        self.assertEqual(int(plan['Prioridad'].eq('Configurar umbrales').sum()),4)

    def test_constant_and_determinism(self):
        data=self.data[self.data.asset_id.eq('M-001')].copy()
        data['temperature_c']=50.
        a=build_maintenance_plan(data,{('M-001','temperature_c'):80},self.ref)
        b=build_maintenance_plan(data,{('M-001','temperature_c'):80},self.ref)
        pd.testing.assert_frame_equal(a,b)
        self.assertEqual(a.iloc[0]['Prioridad'],'Seguimiento sin fecha')
        self.assertTrue(a['Revisar antes de (UTC)'].isna().all())

    def test_config_and_unknown_limit(self):
        for kw in [{'lead_hours':-1},{'lead_hours':np.inf},{'freshness_hours':0},{'planning_days':100}]:
            with self.assertRaises(ValueError):PlanConfig(**kw)
        with self.assertRaises(ValueError):build_maintenance_plan(self.data,{('otra','temperature_c'):80},self.ref)
        with self.assertRaises(ValueError):build_maintenance_plan(self.data,{},pd.NaT)
