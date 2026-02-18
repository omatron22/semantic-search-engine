import sys
from lxml import etree


def extract_text_from_html(file_path):
    """Extract text from HTML or XML file by stripping tags."""
    try:
        with open(file_path, "rb") as f:
            raw = f.read()

        # Try HTML first, fall back to XML
        try:
            tree = etree.HTML(raw)
        except Exception:
            tree = etree.fromstring(raw)

        if tree is None:
            return "Error reading HTML/XML: could not parse file"

        # Walk the tree and collect text with spacing between elements
        parts = []
        for element in tree.iter():
            if element.text and element.text.strip():
                parts.append(element.text.strip())
            if element.tail and element.tail.strip():
                parts.append(element.tail.strip())
        return "\n".join(parts)
    except Exception as e:
        return f"Error reading HTML/XML: {str(e)}"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python parse_html.py <path_to_html_or_xml>")
        sys.exit(1)

    text = extract_text_from_html(sys.argv[1])
    print(text)
