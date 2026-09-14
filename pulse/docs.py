"""Local document evidence with an injectable Pinecone/LangChain retriever."""
from pathlib import Path
import re
from .data import ROOT

class Documentation:
    def __init__(self, root=ROOT, retriever=None):
        self.root, self.retriever = Path(root), retriever

    def search(self, product, query=''):
        if self.retriever is not None:
            return [dict(text=d.page_content, source=d.metadata.get('source','Unknown'),
                         line_start=d.metadata.get('line_start'), line_end=d.metadata.get('line_end'),
                         mode='Pinecone retrieval') for d in self.retriever.invoke(f'{product}: {query}')]
        # Return full product sections, not a fabricated RAG answer.
        found=[]
        for filename in ('product_source_of_truth.md','api_documentation.md','agent_procedures.md','product_faq.md'):
            path=self.root/'data'/filename
            if not path.exists(): continue
            lines=path.read_text().splitlines()
            starts=[i for i,l in enumerate(lines) if l.startswith('## ')] + [len(lines)]
            for a,b in zip(starts,starts[1:]):
                text='\n'.join(lines[a:b])
                if product.casefold() in text.casefold():
                    found.append(dict(source='data/'+filename, line_start=a+1, line_end=b,
                                      text=text, mode='Local document section'))
        return found

    def quote(self, filename, phrase):
        path=self.root/'data'/filename
        if not path.exists(): return None
        for number,line in enumerate(path.read_text().splitlines(),1):
            if phrase.casefold() in line.casefold():
                return dict(source='data/'+filename,line_start=number,line_end=number,text=line.strip())
        return None

# Explicit, narrow demo checks. These are not a general semantic/LLM audit.
CHECKS=[
    dict(id='verification', product='Bank Account Management',title='Pending verification guidance conflicts',
         truth='A bank account remains unavailable for payment until verification succeeds.',
         file='agent_procedures.md', current='may still be used for a payment while verification is pending',
         why='The procedure permits payment before verification succeeds; the authoritative rule requires successful verification first.'),
    dict(id='dates', product='Payment Flex',title='Payment-date availability is overstated',
         truth='Not every calendar date must be selectable.',file='agent_procedures.md',
         current='all dates within the next 30 calendar days',
         why='The procedure promises a 30-day availability window, while the Source of Truth makes date availability conditional on product and account rules.'),
    dict(id='activation', product='Balance Assist Plan',title='Plan activation is described too early',
         truth='A plan is not active until the payment schedule is successfully created.',file='product_faq.md',
         current='Your plan is active after you select the plan terms',
         why='The FAQ treats terms selection as activation, but the authoritative rule requires successful schedule creation.'),
]

def knowledge_gaps(docs):
    gaps=[]
    for rule in CHECKS:
        truth=docs.quote('product_source_of_truth.md',rule['truth'])
        current=docs.quote(rule['file'],rule['current'])
        if truth and current:
            gaps.append({**rule,'truth_evidence':truth,'current_evidence':current})
    return gaps

def draft_update(gap, confirmed):
    if not confirmed:
        raise ValueError('The PM must confirm the gap before drafting.')
    return gap['truth_evidence']['text'].lstrip('- ')

def update_request(gap, wording, reason=None, truth_ref=None):
    return (f"# Documentation Update Request\n\nProduct: {gap['product']}\n"
            f"Document: {gap['current_evidence']['source']}\n\n## Proposed wording\n{wording}\n\n"
            f"## Reason\n{reason if reason is not None else gap['why']}\n\n## Source of Truth\n"
            f"{truth_ref or gap.get('truth_ref') or str(gap['truth_evidence']['source']) + ', line ' + str(gap['truth_evidence']['line_start'])}\n\n"
            f"{gap['truth_evidence']['text']}\n")
