from queue import Queue

class MessageBus:
    def __init__(self):
        self.q = Queue()
    def publish(self, ev):
        self.q.put(ev)
    def poll(self):
        try:
            return self.q.get_nowait()
        except Exception:
            return None
