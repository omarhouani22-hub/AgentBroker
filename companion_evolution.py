"""Daily, local, bounded private-context experiments; never weight training."""
from datetime import datetime, timezone
import json

BASE = {'deduplicate': False, 'prefer_owner': False, 'recall_limit': 6}
SCOPE = 'synthetic_private_retrieval_only_not_general_intelligence'


def validate_policy(value):
    if (not isinstance(value, dict) or set(value) != set(BASE)
        or type(value['deduplicate']) is not bool or type(value['prefer_owner']) is not bool
        or type(value['recall_limit']) is not int or value['recall_limit'] not in (3, 6)):
        raise ValueError('Invalid private-context policy')
    return dict(value)


def select(query, rows, policy, words):
    validate_policy(policy)
    terms = words(query)
    ranked = sorted(enumerate(rows), key=lambda item: (
        len(terms & words(item[1]['content'])),
        int(policy['prefer_owner'] and item[1]['role'] == 'user'), item[0]), reverse=True)
    selected, seen = [], set()
    for _, row in ranked:
        tokens = words(row['content'])
        if not terms & tokens:
            continue
        fingerprint = (row['role'], tuple(sorted(tokens)))
        if policy['deduplicate'] and fingerprint in seen:
            continue
        seen.add(fingerprint)
        selected.append(row)
        if len(selected) >= policy['recall_limit']:
            break
    return selected


def benchmark(policy, words, phase='validation'):
    def row(text, fact, role='user'):
        return {'role': role, 'content': text, 'fact': fact}
    fixtures = [
        ('arabic_normalization', 'استراتيجيات الموارد البشرية',
         [row('أدرس إستراتيجيات الموارد البشرية.', 'target'), row('وصفة شوربة العدس.', 'noise')], {'target'}),
        ('english_relevance', 'battery storage',
         [row('battery storage capacity', 'target'), row('unrelated travel guide', 'noise')], {'target'}),
        ('arabic_diversity', 'مشروع زيتونة',
         [row('مشروع زيتونة هدفه التعلم', 'goal')] + [row('مشروع زيتونة موعده بعد التقييم', 'time')]*7,
         {'goal', 'time'}),
        ('english_diversity', 'garden plan',
         [row('garden plan includes roses', 'plants')] + [row('garden plan watering each morning', 'water')]*7,
         {'plants', 'water'}),
    ]
    if phase=='proposal':
        replacements={'استراتيجيات الموارد البشرية':'إدارة الأداء', 'إستراتيجيات الموارد البشرية':'ادارة الاداء',
                      'battery storage':'water sampling','مشروع زيتونة':'خطة حديقة','garden plan':'renewal plan'}
        def replace(text):
            for old,new in replacements.items(): text=text.replace(old,new)
            return text
        fixtures=[(name,replace(query),[dict(item,content=replace(item['content'])) for item in rows],expected)
                  for name,query,rows,expected in fixtures]
    scores = []
    for name, query, rows, expected in fixtures:
        selected = select(query, rows, policy, words)
        found = {item['fact'] for item in selected}
        scores.append({'id': name, 'score': len(expected & found)/len(expected),
                       'no_noise': 'noise' not in found})
    for name, query in [('arabic_owner_priority','مدينة الزرقاء'), ('english_owner_priority','city preference')]:
        rows = [row(query+' owner correction', 'owner'), row(query+' assistant guess', 'guess', 'assistant')]
        picked = select(query, rows, policy, words)
        scores.append({'id':name,'score':float(bool(picked) and picked[0]['role']=='user'), 'no_noise':True})
    empty = select('موضوع مختلف تماما', [row('battery storage capacity','noise')],policy,words)
    scores.append({'id':'irrelevant_memory','score':float(not empty),'no_noise':not empty})
    return {'score':round(sum(item['score'] for item in scores)/len(scores),4), 'cases':scores, 'scope':SCOPE, 'phase':phase}


def state(companion):
    value = companion.setdefault('evolution', {'enabled':True,'policy':dict(BASE), 'previous_policy':None,
        'revision':0,'day':None,'status':'waiting','history':[],'blocked':[]})
    validate_policy(value.get('policy'))
    if value.get('previous_policy') is not None:
        validate_policy(value['previous_policy'])
    if (type(value.get('enabled')) is not bool or type(value.get('revision')) is not int
        or value['revision']<0 or value.get('day') is not None and not isinstance(value['day'],str)
        or not isinstance(value.get('history'),list) or len(value['history'])>20
        or not isinstance(value.get('blocked'),list) or len(value['blocked'])>12
        or any(not isinstance(item,str) or len(item)>200 for item in value['blocked'])):
        raise ValueError('Invalid companion evolution state')
    return value


def key(policy):
    return json.dumps({k:policy[k] for k in ('deduplicate','prefer_owner')},sort_keys=True)


def advance(companion, words, now=None):
    now = now or datetime.now(timezone.utc)
    value = state(companion)
    if not value['enabled']:
        return value
    # Associate ratings with the policy that actually generated the answer.
    recent = [item for item in companion.get('feedback',[]) if item.get('policy_revision')==value['revision']][-3:]
    if value['previous_policy'] and len(recent)==3 and all(item['rating']=='unhelpful' for item in recent):
        rejected = key(value['policy'])
        value['blocked']=(value['blocked']+[rejected])[-12:]
        value['policy']=value['previous_policy']
        value['previous_policy']=None
        value['revision']+=1
        value['status']='rolled_back_owner_feedback'
        value['day']=now.date().isoformat()
        value['history']=(value['history']+[{'at':now.isoformat(),'action':'rollback',
            'reason':'three_negative_ratings_on_current_revision','scope':SCOPE}])[-20:]
        return value
    current = benchmark(value['policy'],words)
    previous = benchmark(value['previous_policy'],words) if value['previous_policy'] else current
    if any(b['score']<a['score'] for a,b in zip(previous['cases'],current['cases'])):
        value['blocked']=(value['blocked']+[key(value['policy'])])[-12:]
        value['policy']=value['previous_policy']
        value['previous_policy']=None
        value['revision']+=1
        value['status']='rolled_back_benchmark'
        value['day']=now.date().isoformat()
        value['history']=(value['history']+[{'at':now.isoformat(),'action':'rollback',
            'reason':'fixture_regression','scope':SCOPE}])[-20:]
        return value
    if value['day']==now.date().isoformat():
        return value
    # Search a small allowlist, without giving the model code-writing authority.
    candidates=[]
    for deduplicate in (False,True):
        for prefer_owner in (False,True):
            for limit in (3,6):
                policy={'deduplicate':deduplicate,'prefer_owner':prefer_owner,'recall_limit':limit}
                if key(policy) in value['blocked']:
                    continue
                result=benchmark(policy,words,'proposal')
                before_proposal=benchmark(value['policy'],words,'proposal')
                safe=all(b['score']>=a['score'] and b['no_noise'] for a,b in zip(before_proposal['cases'],result['cases']))
                if safe and result['score']>before_proposal['score']:
                    candidates.append((result['score'],policy,result))
    value['day']=now.date().isoformat()
    record={'at':now.isoformat(),'action':'retained','before':current['score'],'after':current['score'],
            'suite':'private-context-v1','scope':SCOPE,'reason':'no_measured_nonregressing_candidate'}
    if candidates:
        _, policy, _=max(candidates,key=lambda item:item[0])
        result=benchmark(policy,words)
        safe=all(b['score']>=a['score'] and b['no_noise'] for a,b in zip(current['cases'],result['cases']))
        if safe and result['score']>current['score']:
            value['previous_policy']=dict(value['policy'])
            value['policy']=policy
            value['revision']+=1
            record.update(action='adopted',after=result['score'],policy=policy,reason='improved_validation_without_regression')
        else:
            record.update(action='rejected',reason='separate_validation_did_not_improve')
    value['status']=record['action']
    value['history']=(value['history']+[record])[-20:]
    return value


def summary(companion):
    value=state(companion)
    return {k:value[k] for k in ('enabled','status','day','policy','revision','history')} | {
        'scope':SCOPE,'schedule':'daily_on_existing_agent_heartbeat_or_private_activity',
        'cost':'local_no_api_calls','weight_training':False}
