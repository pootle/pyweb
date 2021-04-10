import simpleweb

class mymaths():
    def __init__(self):
        self.number_A = 0.0
        self.number_B = 0.0
        self.operation = 'add'

    def valid_ops(self):
        return ('add', 'subtract', 'multiply', 'divide')

    def answer(self):
        if self.operation=='add':
            return self.number_A + self.number_B
        elif self.operation=='subtract':
            return self.number_A - self.number_B
        elif self.operation=='multiply':
            return self.number_A * self.number_B
        elif self.operation=='divide':
            return self.number_A / self.number_B
        else:
            return float('nan')
