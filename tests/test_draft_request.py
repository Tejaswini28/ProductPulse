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

def test_rewrite_prioritizes_requested_style_and_retries_unchanged_output():
    from pulse.knowledge_agent import UpdateDraft
    gap={'truth_ref':'truth:1','truth_evidence':{'text':'Verify before payment.'}}
    class Writer:
        def __init__(self):self.calls=[]
        def with_structured_output(self,*args,**kwargs):return self
        def invoke(self,messages):
            self.calls.append(messages)
            return UpdateDraft(proposed_wording='Verify before payment.' if len(self.calls)==1 else 'Verification is required before payment.',reason='Preserves verification requirement.',truth_ref='truth:1')
    writer=Writer()
    result=generate_update_draft(gap,True,model=writer,feedback='Use formal language.',previous_wording='Verify before payment.')
    assert result['proposed_wording']=='Verification is required before payment.'
    assert len(writer.calls)==2
    assert 'requested style takes precedence' in writer.calls[0][0][1]
    assert 'Use formal language.' in writer.calls[0][1][1]

def test_rewrite_does_not_silently_succeed_with_unchanged_wording():
    from pulse.knowledge_agent import UpdateDraft
    class Writer:
        def with_structured_output(self,*args,**kwargs):return self
        def invoke(self,messages):return UpdateDraft(proposed_wording='Verify before payment.',reason='Preserves rule.',truth_ref='truth:1')
    with pytest.raises(ValueError,match='unchanged wording'):
        generate_update_draft({'truth_ref':'truth:1'},True,model=Writer(),feedback='Shorten.',previous_wording='Verify before payment.')
