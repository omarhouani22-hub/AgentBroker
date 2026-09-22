import json
from unittest.mock import patch, MagicMock
from test_hermes import HermesTests, result, answers
import app
import hermes_pilot as h
import hermes_team as team
import hermes_references as refs

BUNDLE={'status':'ready','excerpts':[{'citation':'R1','file_id':'fixture','name':'Test source',
        'locator':'Page 4','text':'SYNTHETIC_REFERENCE: divide workload by productive hours.', 'sha256':'fixture'}]}

class ReferenceTests(HermesTests):
    def test_reference_access_is_authenticated_and_does_not_call_model(self):
        with patch.object(refs,'fetch_references',return_value=BUNDLE) as fetch, patch.object(h,'invoke') as model:
            self.assertEqual(self.client.get('/hermes/references').status_code,401)
            fetch.assert_not_called()
            self.assertEqual(self.client.get('/hermes/references',headers=self.headers).json,BUNDLE)
            model.assert_not_called()

    def test_training_receives_sources_but_benchmark_does_not(self):
        identity=self.start()
        state=h.read_state(app.db)
        state['experiment'].update(references=BUNDLE,teacher_enabled=True)
        h.write_state(app.db,state)
        skill={'capacity/SKILL.md':'Divide workload by productive hours; see [R1].'}
        with patch.object(h,'invoke',side_effect=[result(answers(True)),result('Explain units'),result('Saved',skill),result(answers(),skill)]) as invoke, patch.object(h,'deepseek_teacher',return_value={'output':'Use [R1].'}) as teacher:
            for _ in range(5): response=self.step(identity)
        self.assertTrue(response.json['experiment']['adopted'])
        self.assertNotIn('SYNTHETIC_REFERENCE',invoke.call_args_list[0].args[1])
        self.assertNotIn('SYNTHETIC_REFERENCE',invoke.call_args_list[-1].args[1])
        self.assertIn('SYNTHETIC_REFERENCE',invoke.call_args_list[1].args[1])
        self.assertIn('SYNTHETIC_REFERENCE',invoke.call_args_list[2].args[1])
        self.assertIn('SYNTHETIC_REFERENCE',teacher.call_args.args[0])
        self.assertEqual(response.json['skill_sources']['capacity/SKILL.md'][0]['locator'],'Page 4')

    def test_missing_or_invented_citations_block_acceptance(self):
        for content in ('No citations.', 'Invented [R9].'):
            valid,_=refs.cited_sources({}, {'capacity/SKILL.md':content},BUNDLE)
            self.assertFalse(valid)

    def test_reference_outage_starts_no_paid_round(self):
        self.client.post('/hermes/team',json={'enabled':True},headers=self.headers)
        with patch.object(app,'clock_identity',return_value=True), patch.object(h,'runtime_ready',return_value=True), patch.object(team,'fetch_references',side_effect=TimeoutError), patch.object(h,'invoke') as model:
            response=self.client.post('/hermes/team/clock',json={})
        self.assertEqual(response.status_code,503)
        self.assertEqual(h.read_state(app.db)['team']['round'],0)
        model.assert_not_called()

    def test_reader_bounds_and_hashes_source_text(self):
        passage={k:v for k,v in BUNDLE['excerpts'][0].items() if k in ('file_id','name','locator','text')}
        response=MagicMock();response.__enter__.return_value=response
        response.read.return_value=json.dumps({'excerpts':[passage]}).encode()
        opener=MagicMock();opener.open.return_value=response
        with patch.object(refs,'build_opener',return_value=opener):
            data=refs.fetch_references(1)
        self.assertEqual(len(data['excerpts'][0]['sha256']),64)
        self.assertEqual(data['excerpts'][0]['citation'],'R1')
