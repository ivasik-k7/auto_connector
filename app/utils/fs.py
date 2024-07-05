class FS:
    def __init__(self, filename) -> None:
        self.filename = filename

    def read(self):
        try:
            with open(self.filename, "r") as file:
                return file.read()
        except FileNotFoundError:
            print(f"Error: File '{self.filename}' not found.")
            return None
        except IOError as e:
            print(f"Error reading file '{self.filename}': {e}")
            return None

    def write(self, content):
        try:
            with open(self.filename, "w") as file:
                file.write(content)
            print(f"Successfully wrote to file '{self.filename}'.")
        except IOError as e:
            print(f"Error writing to file '{self.filename}': {e}")

    def append(self, content):
        current_content = self.read()
        if current_content and content in current_content:
            print(f"Item '{content}' already exists in file '{self.filename}'.")
            return

        try:
            with open(self.filename, "a") as file:
                file.write(content + "\n")
            print(
                f"Successfully appended unique item '{content}' to file '{self.filename}'."
            )
        except IOError as e:
            print(f"Error appending to file '{self.filename}': {e}")
        # try:
        #     with open(self.filename, "a") as file:
        #         file.write(content + "\n")
        #     print(f"Successfully appended to file '{self.filename}'.")
        # except IOError as e:
        #     print(f"Error appending to file '{self.filename}': {e}")
