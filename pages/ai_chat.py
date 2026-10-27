from services.agent_service import AgentService


def show_ai_chat(workspace, question):
    cached = workspace.cache.get(f'segments:{workspace.segment_k}', {})
    agent = AgentService(workspace.active(), workspace.memory, segments=cached.get('customers'), n_clusters=workspace.segment_k)
    try:
        result = agent.ask(question)
        if result.get('verified'):
            result['trace'].update(dataset=workspace.filename, view=workspace.mode, filters=dict(workspace.filters))
        result['followups'] = (['Show that as a chart', 'Show only 3'] if result.get('sql') else ['Show statistics', 'Generate insights'])
        workspace.chat_results.append({'question': question, 'result': result})
        workspace.chat_results = workspace.chat_results[-20:]
        return result
    finally:
        agent.close()
