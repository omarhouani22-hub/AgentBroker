import copy
import os
import tempfile
import sqlite3
from datetime import datetime,timezone,timedelta
import unittest
from unittest.mock import patch
import companion_evolution as e
import moltbook as m
from app import app


class EvolutionTests(unittest.TestCase):
    def test_real_local_candidate_improves_distinct_suites(self):
        owner={}
        before=e.benchmark(e.BASE,m.memory_words)
        result=e.advance(owner,m.memory_words)
        self.assertEqual(result['status'],'adopted')
        self.assertGreater(e.benchmark(result['policy'],m.memory_words)['score'],before['score'])
        for phase in ('proposal','validation'):
            after=e.benchmark(result['policy'],m.memory_words,phase)
            initial=e.benchmark(e.BASE,m.memory_words,phase)
            self.assertTrue(all(b['score']>=a['score'] for a,b in zip(initial['cases'],after['cases'])))

    def test_daily_idempotence_and_encrypted_state_shape(self):
        owner={};now=datetime(2026,10,1,tzinfo=timezone.utc)
        e.advance(owner,m.memory_words,now)
        snapshot=copy.deepcopy(owner)
        e.advance(owner,m.memory_words,now)
        self.assertEqual(owner,snapshot)
        e.advance(owner,m.memory_words,now+timedelta(days=1))
        self.assertEqual(len(owner['evolution']['history']),2)
        self.assertEqual(owner['evolution']['status'],'retained')

    def test_negative_feedback_rolls_back_and_does_not_readopt_same_family(self):
        owner={};now=datetime(2026,10,1,tzinfo=timezone.utc)
        result=e.advance(owner,m.memory_words,now)
        old=copy.deepcopy(result['previous_policy'])
        owner['feedback']=[{'rating':'unhelpful','policy_revision':result['revision']} for _ in range(3)]
        e.advance(owner,m.memory_words,now)
        self.assertEqual(result['status'],'rolled_back_owner_feedback')
        self.assertEqual(result['policy'],old)
        e.advance(owner,m.memory_words,now+timedelta(days=1))
        self.assertNotEqual(result['policy'],{'deduplicate':True,'prefer_owner':True,'recall_limit':6})

    def test_bad_validation_rejects_a_promising_proposal(self):
        original=e.benchmark
        def check(policy,words,phase='validation'):
            result=original(policy,words,phase)
            if phase=='validation' and policy!=e.BASE:
                result['score']=0;result['cases'][0]['score']=0
            return result
        with patch.object(e,'benchmark',side_effect=check):
            result=e.advance({},m.memory_words)
        self.assertEqual(result['status'],'rejected')
        self.assertEqual(result['policy'],e.BASE)

    def test_disabled_and_malformed_policy(self):
        owner={};e.state(owner)['enabled']=False
        result=e.advance(owner,m.memory_words)
        self.assertEqual(result['status'],'waiting')
        with self.assertRaises(ValueError):e.validate_policy(dict(e.BASE,recall_limit=500))

    def test_context_preserves_history_and_keeps_public_requests_separate(self):
        owner={'messages':[{'id':'x','role':'user','content':'مشروع زيتونة'}],
               'archive':[{'id':'old','role':'user','content':'مشروع زيتونة يحتاج اختباراً.'}]}
        old=copy.deepcopy(owner['archive'])
        context=m.companion_context(owner,'reply')
        self.assertEqual(owner['archive'],old)
        self.assertTrue(context['_companion'])
        self.assertNotIn('evolution',context)

    def test_control_requires_owner_and_persists_pause(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,{'AGENT_DB_PATH':directory+'/state.db','AGENT_ACCESS_TOKEN':'test-only-token'}):
            client=app.test_client()
            self.assertEqual(client.post('/companion/evolution',json={'enabled':True}).status_code,401)
            headers={'Authorization':'Bearer test-only-token'}
            accepted=client.post('/companion/evolution',json={'enabled':True},headers=headers)
            self.assertEqual(accepted.status_code,200)
            self.assertEqual(accepted.json['learning']['evolution']['status'],'adopted')
            paused=client.post('/companion/evolution',json={'enabled':False},headers=headers)
            self.assertFalse(paused.json['learning']['evolution']['enabled'])
            self.assertFalse(client.get('/companion/messages',headers=headers).json['learning']['evolution']['enabled'])

    def test_proactivity_waits_for_reply_then_proposes_after_cooldown(self):
        with tempfile.TemporaryDirectory() as directory:
            db=lambda:sqlite3.connect(directory+'/state.db')
            state=m.dialogue_state(db)
            output={'skip':False,'content':'خلينا نجرب فكرة مفيدة: شو مهارة بتحب تتعلمها هالأسبوع؟','lesson':''}
            with patch.object(m,'dialogue_model_configured',return_value=True),patch.object(m,'free_dialogue_json',return_value=output) as generate,patch.object(m,'api') as public:
                m.initiate_companion(db,state)
                owner=state['companion']
                owner['last_initiative_at']-=7*3600
                m.initiate_companion(db,state)
                self.assertEqual(generate.call_count,1)
                m.append_companion(owner,'user','حاب أتعلم مهارة مفيدة.')
                m.append_companion(owner,'assistant','ممكن نختار مهارة واحدة ونحط تجربة بسيطة.')
                m.initiate_companion(db,state)
                self.assertEqual(generate.call_count,2)
                self.assertEqual(owner['messages'][-1]['initiative_kind'],'suggestion')
                self.assertIn('concrete next step',generate.call_args.args[0]['task'])
                owner['last_initiative_at']-=7*3600
                m.append_companion(owner,'user','تمام')
                m.append_companion(owner,'assistant','ممتاز، نتابع بعد التجربة.')
                m.initiate_companion(db,state)
                self.assertEqual(generate.call_count,2)
                public.assert_not_called()

    def test_proactivity_never_interrupts_an_unanswered_user(self):
        with tempfile.TemporaryDirectory() as directory:
            db=lambda:sqlite3.connect(directory+'/state.db')
            state=m.dialogue_state(db)
            m.append_companion(m.companion_state(state),'user','عندي سؤال مهم.')
            with patch.object(m,'dialogue_model_configured',return_value=True),patch.object(m,'free_dialogue_json') as generate:
                m.initiate_companion(db,state)
            generate.assert_not_called()


if __name__=='__main__':unittest.main()
