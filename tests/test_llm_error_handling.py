import sys,json,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx,pytest
from langchain_core.messages import HumanMessage,AIMessage,ToolMessage
from langchain_openai.chat_models.base import (
    OpenAIAuthenticationError,OpenAIRateLimitError,OpenAIInvalidRequestError,
    OpenAIContextOverflowError,OpenAIAPIError,
)
from pulse.errors import classify,describe
from pulse.agent import execute_agent,validate_investigation

def openai_error(cls,message,status=400):
    response=httpx.Response(status_code=status,request=httpx.Request('POST','https://api.openai.com/v1/chat/completions'))
    return cls(message=message,response=response,body=None)

# ---- classify(): each of the 7 categories -------------------------------

def test_classify_authentication():
    assert classify(openai_error(OpenAIAuthenticationError,'Incorrect API key',401))=='authentication'

def test_classify_rate_limit():
    assert classify(openai_error(OpenAIRateLimitError,'Rate limit reached',429))=='rate_limit'

def test_classify_invalid_request():
    assert classify(openai_error(OpenAIInvalidRequestError,'Invalid value for temperature',400))=='invalid_request'

def test_classify_context_limit():
    assert classify(openai_error(OpenAIContextOverflowError,'This model\'s maximum context length is 128000 tokens',400))=='context_limit'

def test_classify_malformed_tool_request():
    assert classify(openai_error(OpenAIInvalidRequestError,"Invalid 'tools[0].function.name'",400))=='malformed_tool_request'

def test_classify_temporary_service_failure():
    assert classify(openai_error(OpenAIAPIError,'The server had an error',500))=='temporary_service_failure'

def test_classify_unknown_does_not_assume_credentials():
    # A plain, unrecognized exception must not be assumed to be an auth problem.
    assert classify(RuntimeError('something unexpected'))=='unknown'

# ---- describe(): PM message stays generic, technical detail preserved ----

def test_describe_never_leaks_provider_detail_into_pm_message():
    error=openai_error(OpenAIAuthenticationError,'sk-leaked-secret-abc123 is invalid',401)
    failure=describe(error,stage='investigation_analysis',model='gpt-4.1-mini')
    assert failure['status']=='unavailable'
    assert 'sk-leaked-secret' not in failure['message']
    assert failure['retryable'] is False  # auth is not recoverable by retrying
    assert 'sk-leaked-secret' in failure['technical_error']  # real detail kept, just not PM-facing
    assert failure['category']=='authentication'

def test_describe_marks_rate_limit_and_temporary_failures_retryable():
    assert describe(openai_error(OpenAIRateLimitError,'x',429),'s')['retryable'] is True
    assert describe(openai_error(OpenAIAPIError,'x',500),'s')['retryable'] is True
    assert describe(openai_error(OpenAIInvalidRequestError,'x',400),'s')['retryable'] is False
    assert describe(openai_error(OpenAIAuthenticationError,'x',401),'s')['retryable'] is False

# ---- execute_agent(): state preservation + no pointless retry loop -------

class FakeGraphAgent:
    """Minimal stand-in for the LangGraph agent object execute_agent drives."""
    def __init__(self,states,error=None):
        self.states=states;self.error=error;self.stream_calls=0
    def stream(self,*a,**kw):
        self.stream_calls+=1
        for state in self.states:
            yield state
        if self.error:
            raise self.error

def complaint_tool_message():
    payload={'records':[{'_evidence':{'source':'data/product_health.csv','data_row':2,'evidence_id':'product_health.csv:row-2'},
        'signal_type':'complaint','product_name':'Bank Account Management','complaint_text':'Verification failed repeatedly.'}]}
    return ToolMessage(name='get_complaints',content=json.dumps(payload),tool_call_id='call-1')

def test_service_failure_is_classified_not_generic():
    states=[{'messages':[HumanMessage(content='investigate'),AIMessage(content='',tool_calls=[{'name':'get_complaints','args':{},'id':'call-1'}]),complaint_tool_message()]}]
    agent=FakeGraphAgent(states,error=openai_error(OpenAIRateLimitError,'Rate limit reached',429))
    run=execute_agent('investigate the complaint',agent,validate_investigation,stage='investigation_analysis',model_name='gpt-4.1-mini')
    assert run['status']=='unavailable'
    assert run['retryable'] is True
    assert run['failure_category']=='rate_limit'
    assert 'Rate limit reached' not in run['error']  # PM message stays generic
    assert 'Rate limit reached' in run['technical_error']

def test_non_retryable_failure_is_not_retried_by_our_own_code():
    states=[{'messages':[HumanMessage(content='investigate')]}]
    agent=FakeGraphAgent(states,error=openai_error(OpenAIInvalidRequestError,'bad request',400))
    run=execute_agent('investigate',agent,validate_investigation,stage='investigation_analysis')
    assert run['status']=='unavailable'
    assert run['retryable'] is False
    assert agent.stream_calls==1  # execute_agent does not loop/retry itself — that already happens at the transport layer

def test_evidence_gathered_before_failure_is_preserved():
    states=[{'messages':[HumanMessage(content='investigate'),AIMessage(content='',tool_calls=[{'name':'get_complaints','args':{},'id':'call-1'}]),complaint_tool_message()]}]
    agent=FakeGraphAgent(states,error=openai_error(OpenAIAPIError,'server error',500))
    run=execute_agent('investigate the complaint',agent,validate_investigation,stage='investigation_analysis')
    assert run['status']=='unavailable'
    assert len(run['messages'])==3  # the successful tool round-trip is retained, not discarded
    assert any('complaint_text' in str(r) for r in run['evidence'].values())  # the complaint evidence survives the later crash

def test_retry_reuses_original_investigation_inputs(monkeypatch):
    # Confirms the fields a PM-triggered retry needs (product/complaint/customer/day)
    # are present on a failed run, so a retry never requires re-entering them.
    from pulse.investigation_service import investigate_with_agent
    class RaisingAgent:
        def stream(self,*a,**kw):
            raise openai_error(OpenAIAPIError,'server error',500)
    run=investigate_with_agent('Bank Account Management','Verification failed repeatedly',customer='C1001',agent=RaisingAgent())
    assert run['status']=='unavailable'
    assert run['product']=='Bank Account Management'
    assert run['complaint']=='Verification failed repeatedly'
    assert run['customer']=='C1001'

def test_pm_message_never_contains_raw_exception_type_name():
    from pulse.investigation_service import investigate_with_agent
    class RaisingAgent:
        def stream(self,*a,**kw):
            raise openai_error(OpenAIContextOverflowError,'maximum context length exceeded',400)
    run=investigate_with_agent('Bank Account Management','Verification failed',agent=RaisingAgent())
    assert 'OpenAI' not in run['error'] and 'Error' not in run['error']
    assert run['status']=='unavailable' and run['retryable'] is False
