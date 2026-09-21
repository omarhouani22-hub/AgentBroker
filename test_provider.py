import io,json,os,unittest
from unittest.mock import patch
import app as b
class ProviderTests(unittest.TestCase):
 def call(self, env, result=None):
  result=result or {'choices':[{'finish_reason':'stop','message':{'content':'OK'}}]}
  with patch.dict(os.environ,env,clear=True), patch.object(b.model_transport,'open',return_value=io.BytesIO(json.dumps(result).encode())) as opened:
   answer=b.model_call([{'role':'user','content':'test'}])
   req=opened.call_args.args[0]
   return answer,req,json.loads(req.data)
 def test_legacy_deepseek(self):
  _,req,payload=self.call({'DEEPSEEK_API_KEY':'legacy-key'})
  self.assertEqual(req.full_url,'https://api.deepseek.com/chat/completions')
  self.assertEqual(req.get_header('Authorization'),'Bearer legacy-key')
  self.assertEqual(payload['model'],'deepseek-chat')
 def test_custom_isolated(self):
  _,req,payload=self.call({'LLM_PROVIDER':'openai-compatible','LLM_BASE_URL':'https://example.com/v1/','LLM_MODEL':'chosen-model','LLM_API_KEY':'new-key','DEEPSEEK_API_KEY':'never-send','LLM_TOKEN_PARAMETER':'max_completion_tokens'})
  self.assertEqual(req.full_url,'https://example.com/v1/chat/completions')
  self.assertEqual(req.get_header('Authorization'),'Bearer new-key')
  self.assertEqual(payload['max_completion_tokens'],1800)
  self.assertNotIn('max_tokens',payload)
 def test_local_without_key(self):
  _,req,_=self.call({'LLM_PROVIDER':'openai-compatible','LLM_BASE_URL':'http://127.0.0.1:11434/v1','LLM_MODEL':'local-model'})
  self.assertIsNone(req.get_header('Authorization'))
 def test_invalid_config_no_network(self):
  base={'LLM_PROVIDER':'openai-compatible','LLM_BASE_URL':'https://example.com/v1','LLM_MODEL':'test','LLM_API_KEY':'new-key'}
  for changes in ({'LLM_API_KEY':'','DEEPSEEK_API_KEY':'never-use'}, {'LLM_BASE_URL':'http://example.com/v1'}, {'LLM_BASE_URL':'https://user:pass@example.com/v1'}, {'LLM_BASE_URL':'https://example.com/v1?key=x'}, {'LLM_MODEL':''}, {'LLM_PROVIDER':'unknown'}, {'LLM_API_KEY':'has\nnewline'}):
   with self.subTest(changes=changes),patch.dict(os.environ,{**base,**changes},clear=True),patch.object(b.model_transport,'open') as opened:
    with self.assertRaises(ValueError):b.model_call([])
    opened.assert_not_called()
 def test_incomplete_and_empty_rejected(self):
  for reason,content in [('length','partial'),('stop',''),('stop',None)]:
   with self.assertRaises(ValueError):self.call({'DEEPSEEK_API_KEY':'key'},{'choices':[{'finish_reason':reason,'message':{'content':content}}]})
 def test_redirect_blocked(self):
  self.assertIsNone(b.NoModelRedirect().redirect_request(None,None,307,'redirect',{},'https://other.example'))
 def test_state_survives_provider_switch(self):
  import tempfile
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'AGENT_DB_PATH':d+'/state.db'}):
   state={'version':1,'policy':b.BASE_RETRIEVAL,'history':[],'day':'2026-09-21','stage':4,'status':'completed','experiment':{}}
   b.write_learning_state(state)
   with patch.dict(os.environ,{'LLM_PROVIDER':'openai-compatible','LLM_MODEL':'new-model'}):
    self.assertEqual(b.read_learning_state()['policy'],state['policy'])
    self.assertEqual(b.read_learning_state()['status'],'completed')
if __name__=='__main__':unittest.main()
