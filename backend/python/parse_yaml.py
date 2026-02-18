import sys
import yaml


def extract_text_from_yaml(yaml_path):
    """Extract text from YAML file by flattening to key-value pairs."""
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        def flatten(obj, prefix=""):
            lines = []
            if isinstance(obj, dict):
                for key, value in obj.items():
                    full_key = f"{prefix}.{key}" if prefix else key
                    if isinstance(value, (dict, list)):
                        lines.extend(flatten(value, full_key))
                    else:
                        lines.append(f"{full_key}: {value}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    lines.extend(flatten(item, f"{prefix}[{i}]"))
            else:
                lines.append(str(obj))
            return lines

        text_lines = flatten(data)
        return "\n".join(text_lines).strip()
    except Exception as e:
        return f"Error reading YAML: {str(e)}"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python parse_yaml.py <path_to_yaml>")
        sys.exit(1)

    text = extract_text_from_yaml(sys.argv[1])
    print(text)
