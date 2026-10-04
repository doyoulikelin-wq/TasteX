import copy
import json
from pathlib import Path
import unittest
from tastex.validation import validate_brief, require_valid, ValidationError

ROOT = Path(__file__).resolve().parents[1]

class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.brief = json.loads((ROOT / 'cases/kiwi-jerky/brief.json').read_text())

    def invalid(self, b):
        result = validate_brief(b)
        self.assertFalse(result['valid'], result)
        with self.assertRaises(ValidationError): require_valid(b)

    def test_unknowns_are_explicit_and_do_not_become_passes(self):
        result = validate_brief(self.brief)
        self.assertTrue(result['valid'])
        self.assertGreater(len(result['unresolved']), 15)
        self.assertIsNone(self.brief['targets'][1]['acceptance'])

    def test_required_sections_and_nested_types(self):
        for key in ('product','targets','ingredients','constraints','assumptions','routes','design'):
            for value in (None, False, 'invalid', 1):
                with self.subTest(key=key, value=value):
                    b=copy.deepcopy(self.brief); b[key]=value; self.invalid(b)

    def test_no_nan_negative_bool_or_zero_mass_basis(self):
        for value in (float('nan'), float('inf'), 10**1000, -1, True, 0, None, [], '100'):
            b=copy.deepcopy(self.brief); b['design']['basis_g']=value; self.invalid(b)

    def test_duplicate_identity_or_factor_keys_rejected(self):
        b=copy.deepcopy(self.brief); b['ingredients'][1]['key']='base'; self.invalid(b)
        b=copy.deepcopy(self.brief); b['design']['constants'].append({'key':'kiwi','grams_per_basis':1}); self.invalid(b)
        b=copy.deepcopy(self.brief); b['ingredients'].append(dict(b['ingredients'][0],key='unused')); self.invalid(b)

    def test_two_selected_routes_and_unknown_reference_rejected(self):
        b=copy.deepcopy(self.brief); b['routes'][1]['status']='selected_for_screening'; self.invalid(b)
        b=copy.deepcopy(self.brief); b['ingredients'][0]['reference_id']='missing'; self.invalid(b)
        b=copy.deepcopy(self.brief); b['ingredients'][3]['identity_relation']='exact'; self.invalid(b)

    def test_explicit_nulls_and_all_target_dimensions_required(self):
        b=copy.deepcopy(self.brief); del b['targets'][0]['acceptance']; self.invalid(b)
        b=copy.deepcopy(self.brief); b['targets'][0]['acceptance']={}; self.invalid(b)
        b=copy.deepcopy(self.brief); b['design']['dimensions'].remove('bitterness'); self.invalid(b)
        b=copy.deepcopy(self.brief); del b['product']['storage_requirement']; self.invalid(b)

    def test_cannot_sneak_path_into_case_id(self):
        for value in ('../case','/absolute','', 'a/b'):
            b=copy.deepcopy(self.brief); b['case_id']=value; self.invalid(b)

    def test_transfer_case_and_no_input_mutation(self):
        before=copy.deepcopy(self.brief); validate_brief(self.brief); self.assertEqual(self.brief,before)
        b=json.loads((ROOT/'benchmarks/transfer-brief.json').read_text()); self.assertTrue(validate_brief(b)['valid'])

if __name__=='__main__': unittest.main()
