

class UndoStack():
    def __init__(self):
        self.history = []
        self.index = None

    def push(self, callback, value):
        self.history.append([callback, value])
        if self.index is None:
            self.index = 0
        else:
            self.index += 1

    def undo(self):
        self.history[self.index][0]('undo', self.history[self.index][1])
        self.index -= 1
    

undo_stack = UndoStack()