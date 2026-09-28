"""Provider integrity regression tests; no live model requests."""
import io,json,os,tempfile,unittest
from unittest.mock import patch
import team_provider as team

def reply(reason='stop',content='Complete answer [S1].'):
 return {'choices':[{'finish_reason':reason,'message':{'content':content}}]}
class TeamResponseTests(unittest.TestCase):
 def invoke(self,body):
  raw=body if isinstance(body,bytes) else json.dumps(body).encode()
  with patch.object(team,'urlopen',return_value=io.BytesIO(raw)) as net:
   value=team._call('https://example.invalid/v1','fake','fake',[],'max_tokens')
  return value,net.call_count
 def test_completed_unchanged(self):self.assertEqual(self.invoke(reply()),('Complete answer [S1].',1))
 def test_partial_filtered_or_tool_answers_rejected(self):
  for reason in ('length','content_filter','tool_calls',None):
   with self.subTest(reason=reason),self.assertRaises(ValueError):self.invoke(reply(reason))
 def test_missing_reason_rejected(self):
  body=reply();del body['choices'][0]['finish_reason']
  with self.assertRaises(ValueError):self.invoke(body)
 def test_malformed_shapes_rejected(self):
  for body in ([],{}, {'choices':[]},{'choices':[None]},{'choices':[{'finish_reason':'stop','message':None}]}):
   with self.subTest(body=body),self.assertRaises(ValueError):self.invoke(body)
 def test_empty_rejected(self):
  for content in ('',' ',None):
   with self.subTest(content=content),self.assertRaises(ValueError):self.invoke(reply(content=content))
 def test_oversize_rejected(self):
  with self.assertRaises(ValueError):self.invoke(json.dumps(reply()).encode()+b' '*200001)
 def test_invalid_not_retried(self):
  with patch.object(team,'urlopen',return_value=io.BytesIO(json.dumps(reply('length')).encode())) as net,patch.object(team.time,'sleep') as wait:
   with self.assertRaises(ValueError):team._call('https://example.invalid','fake','fake',[],'max_tokens')
   self.assertEqual(net.call_count,1);wait.assert_not_called()
 def test_truncated_research_not_saved(self):
  import app
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'AGENT_DB_PATH':d+'/test.db','AGENT_ACCESS_TOKEN':'x'*32,'DUAL_MODEL_MODE':'true','DEEPSEEK_API_KEY':'fake','TAVILY_API_KEY':'fake'},clear=True),patch.object(app,'search_web',return_value=[{'title':'Synthetic','url':'https://example.invalid','content':'Test evidence'}]),patch.object(team,'urlopen',return_value=io.BytesIO(json.dumps(reply('length')).encode())):
   client=app.app.test_client();headers={'Authorization':'Bearer '+'x'*32}
   response=client.post('/runs',json={'goal':'Synthetic integrity check'},headers=headers)
   self.assertEqual(response.status_code,502);self.assertEqual(response.get_json()['status'],'failed')
   self.assertEqual(client.get('/knowledge',headers=headers).get_json(),[])
 def test_incomplete_review_not_a_lesson(self):
  with patch.dict(os.environ,{'DEEPSEEK_API_KEY':'fake','OPENAI_API_KEY':'fake','DUAL_MODEL_MODE':'true'},clear=True),patch.object(team,'_recent_lessons',return_value=[]),patch.object(team,'_save_lesson') as save,patch.object(team,'urlopen',side_effect=[io.BytesIO(json.dumps(reply()).encode()),io.BytesIO(json.dumps(reply('length')).encode())]) as net:
   result=team.dual_model_call([{'role':'user','content':'Synthetic question'}])
   self.assertEqual(result['team_status'],'draft_fallback');self.assertEqual(result['content'],'Complete answer [S1].');save.assert_not_called()
   self.assertEqual(net.call_count,2)
if __name__=='__main__':unittest.main()
