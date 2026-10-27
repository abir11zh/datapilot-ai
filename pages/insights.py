from services.llm_service import LLMService, LLMError
import logging


def show_insights(workspace, summarize=False):
    analyses = workspace.insights()
    facts = [a['title'] + ': ' + ' '.join(a['facts']) for a in analyses]
    summary = ' '.join(facts[:5])
    source = 'Calculated evidence'
    if summarize:
        try:
            summary = LLMService().summarize_facts(facts)
            source = 'AI-selected calculated evidence'
        except (LLMError, ValueError):
            logging.getLogger(__name__).warning('Insight summary unavailable; using calculated facts')
            source = 'Calculated evidence; AI selection is unavailable. Every finding below remains calculated from your data.'
    return {'analyses': analyses, 'summary': summary, 'source': source}
