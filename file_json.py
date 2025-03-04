import json

class FileJson:
    def __init__(self, file):
        self.file = file
        self.data = self.read_json_file()

    def read_json_file(self):
        try:
            with open(self.file, 'r', encoding='utf-8') as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            self.data = {}
            self.write_json_file()
            return self.data

    def write_json_file(self):
        with open(self.file, 'w', encoding='utf-8') as file:
            json.dump(self.data, file, indent=4, ensure_ascii=False)