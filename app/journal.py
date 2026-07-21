class Journal:
    def __init__(self):
        self.entries = []
    
    def save(self, prediction):
        self.entries.append(prediction)
        return True
    
    def get_all(self):
        return self.entries
