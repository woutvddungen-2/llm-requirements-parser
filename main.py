from pathlib import Path

from src.parser import extract_requirements_json


def main() -> None:
    input_path = Path("examples/example1.txt")
    requirement_text = input_path.read_text(encoding="utf-8")

    result = extract_requirements_json(requirement_text)

    print(result)


if __name__ == "__main__":
    main()