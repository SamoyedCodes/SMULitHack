"""Synthetic source and response fixtures. Expected labels live in a separate answer key."""
from backend.documents import save_pages
from backend.evidence import apply_extraction
from backend.models import (Document, Page, Span, Citation, Extraction, FindingDraft,
                            CommercialProvision, SupportReview, Verdict, ConflictDraft)

SME='Acme Pte Ltd'

def seed(config,store,id='a',exclusive=True,mode='live',start='2026-01-01',end='2026-12-31',product='espresso machines',exceptions=None,missing=None,channel='retail stores'):
    text=f'1. Acme Pte Ltd grants Distributor {id} {"exclusive" if exclusive else "non-exclusive"} distribution rights for {product} in Singapore, through {channel}, to commercial customers. The rights apply from {start} to {end}. '+(' '.join(exceptions or [])) + (' Products means the items listed in Schedule 1.' if missing else '')
    span=Span(id=f'{id}:p1:s0',document_id=id,page=1,text=text,bbox=[40,40,550,130],source='native',clause='1')
    pages=[Page(number=1,width=600,height=800,spans=[span])]
    citation=Citation(document_id=id,span_ids=[span.id],quote=text)
    grant=CommercialProvision(id=id+'-grant',grantor=SME,beneficiary='Distributor '+id,activity='distribution',kind='distribution',
        exclusive=exclusive,product=product,territory='Singapore',channel=channel,customers='commercial customers',starts_on=start,ends_on=end,
        citations=[citation],exceptions=exceptions or [],missing_context=missing or [])
    party=FindingDraft(id=id+'-party',field='parties',value=SME+' and Distributor '+id,citations=[citation])
    extraction=Extraction(title='Synthetic',parties=[SME,'Distributor '+id],provisions=[grant],findings=[party])
    reviews=SupportReview(verdicts=[Verdict(item_id=x.id,status='supported',reason='Synthetic fixture support') for x in (grant,party)])
    doc=Document(id=id,filename=f'SYNTHETIC-{id}.pdf',title='Synthetic',sha256='hash-'+id,mode=mode,
                 status='needs_review',page_count=1,pages_read=1,pages_analyzed=1,created_at='2026-09-05T00:00:00Z',model='fake',version='fixture')
    doc=apply_extraction(doc,extraction,reviews,pages)
    store.put_document(doc,'cache:'+id)
    save_pages(config.directory(id)/'pages.json',pages)
    return doc,pages


def draft_for(a,b,pages,status='potential_conflict',time='yes',missing=None,exception=None):
    citations=[Citation(document_id=d.id,span_ids=[pages[d.id][0].spans[0].id],quote=pages[d.id][0].spans[0].text) for d in (a,b)]
    dimensions={'product':'The espresso-machine scopes overlap.','territory':'Both concern Singapore.',
                'activity':'Both grant distribution rights.','channel':'The stated sales channels are compared.',
                'customers':'Both concern commercial customers.','parties':'Acme Pte Ltd is grantor in both agreements.',
                'time':'The expressly stated rights periods overlap.' if time=='yes' else 'The applicable period is unresolved.'}
    return ConflictDraft(status=status,documents=[a.id,b.id],scope_comparison=dimensions,
        citations=citations,dimension_citations={k:citations for k in dimensions},time_overlap=time,
        exceptions=[exception] if exception else [],exception_citations=[[citations[0]]] if exception else [],
        missing_facts=missing or [],explanation='These distribution grants may be incompatible.' if status=='potential_conflict' else 'The express channel exception resolves this particular rule.' if status=='no_conflict_identified_for_this_rule' else 'Consent or scope remains unestablished.',
        lawyer_question='Does exercising the second grant require consent under the first agreement?')


class FakeComparison:
    def __init__(self,status='potential_conflict',callback=None):self.status,self.callback,self.calls=status,callback,0
    def compare(self,payload):
        self.calls+=1
        if self.callback:self.callback()
        citations=[]
        for d in payload['documents']:
            citations.extend(Citation.model_validate(c) for c in d['provisions'][0]['citations'])
        dimensions={k:'Synthetic comparison of the cited distribution clauses.' for k in ['product','territory','activity','channel','customers','parties','time']}
        return ConflictDraft(status=self.status,documents=[d['id'] for d in payload['documents']],scope_comparison=dimensions,
             dimension_citations={k:citations for k in dimensions},time_overlap='yes',citations=citations,exceptions=[],
             missing_facts=[],explanation='Synthetic potentially incompatible grants.',lawyer_question='Does the later grant require consent?')
