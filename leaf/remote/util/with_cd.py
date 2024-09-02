import os


class WithCD:
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        self.saved_path = os.getcwd()
        os.chdir(self.path)

    def __exit__(self, *args):
        os.chdir(self.saved_path)
