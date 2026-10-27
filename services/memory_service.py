class MemoryService:
    """Bounded per-session conversation. UI state lives in the web server session."""
    def __init__(self):
        self.memory = []
        self.last_result = None
        self.last_plan = None

    def add(self, role, content, generated_sql=None, result_summary=None, visualization=None):
        self.memory.append(dict(role=role, content=content, generated_sql=generated_sql,
                                result_summary=result_summary, visualization=visualization))
        self.memory = self.memory[-40:]

    def get_all(self):
        return list(self.memory)

    def clear(self):
        self.memory.clear()
        self.last_result = None
        self.last_plan = None
