import json
import httpx
import pytest
from langchain_openai import ChatOpenAI
from pulse.knowledge_agent import generate_update_draft

def test_draft_uses_valid_tool_request_and_keeps_source_reference():
    calls=[]
    gap={'truth_ref':'data/product_source_of_truth.md:lines-10-12','truth_evidence':{'text':'Verify before payment.'},'why':'Procedure allows premature payment.'}
    def respond(request):
        body=json.loads(request.content);calls.append(body)
        if 'parallel_tool_calls' in body and not body.get('tools'):
            return httpx.Response(400,json={'error':{'message':'parallel_tool_calls requires tools','type':'invalid_request_error','param':'parallel_tool_calls'}})
        tool=body['tools'][0]['function']['name']
        return httpx.Response(200,json={'id':'test-draft','object':'chat.completion','created':0,'model':'gpt-4.1-mini',
            'choices':[{'index':0,'finish_reason':'tool_calls','message':{'role':'assistant','content':None,'tool_calls':[{
                'id':'draft-1','type':'function','function':{'name':tool,'arguments':json.dumps({'proposed_wording':'Verify before payment.','reason':'Match the authoritative rule.','truth_ref':gap['truth_ref']})}}]}}]})
    model=ChatOpenAI(model='gpt-4.1-mini',api_key='test-only',http_client=httpx.Client(transport=httpx.MockTransport(respond)),
        model_kwargs={'parallel_tool_calls':False},max_retries=0)
    with pytest.raises(ValueError,match='PM must confirm'):generate_update_draft(gap,False,model=model)
    assert not calls
    result=generate_update_draft(gap,True,model=model)
    assert len(calls)==1
    assert result=={'proposed_wording':'Verify before payment.','reason':'Match the authoritative rule.','truth_ref':gap['truth_ref']}
