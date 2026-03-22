

class UndoStack():
    def __init__(self):
        self.history = [] # list of each undo/redo step, each element is a list of [undo_callback, undo_value, redo_callback, redo_value]
        self.index = -1 # index should always point to the element in history that will be executed when undo() is called. -1 > empy history

        # references to undo/redo menu items. Main window will set these
        self.undo_action = None
        self.redo_action = None

    def push(self, undo_callback, undo_value, redo_callback, redo_value):
        # discard steps after current point, in case index is not at the end of the stack
        self.history = self.history[:self.index+1]
        self.redo_action.setEnabled(False)

        self.history.append([undo_callback, undo_value, redo_callback, redo_value])
        self.index += 1
        self.undo_action.setEnabled(True)

    def undo(self):
        self.history[self.index][0](self.history[self.index][1])
        self.index -= 1
        if self.index < 0:
            self.undo_action.setEnabled(False)
        self.redo_action.setEnabled(True)

    def redo(self):
        self.index += 1
        self.history[self.index][2](self.history[self.index][3])
        self.undo_action.setEnabled(True)
        if self.index > (len(self.history) - 2):
            self.redo_action.setEnabled(False)

    def clear(self):
        self.history = []
        self.index = -1
        self.undo_action.setEnabled(False)
        self.redo_action.setEnabled(False)

undo_stack = UndoStack()