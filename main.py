from src.parser import extract_requirements_json

# read the text file
with open("example_diemen.txt", "r", encoding="utf-8") as f:
    requirement_text = f.read()

# parse requirements
result = extract_requirements_json(requirement_text)

print(result)