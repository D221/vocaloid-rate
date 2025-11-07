import json
import re
from pathlib import Path

JS_DIR = Path(__file__).parent.parent / "app" / "static" / "js"
TRANSLATIONS_FILE = Path(__file__).parent.parent / "locales" / "js_translations.json"


def extract_js_strings():
    extracted_strings = set()
    for js_file in JS_DIR.rglob("*.js"):
        content = js_file.read_text(encoding="utf-8")
        # Regex to find _('...') or _("...")
        single_quote_matches = re.findall(r"_\('([^']*)'\)", content)
        double_quote_matches = re.findall(r"_\(\"([^\"]*)\"\)", content)
        extracted_strings.update(single_quote_matches)
        extracted_strings.update(double_quote_matches)
        extracted_strings.update(single_quote_matches)
        extracted_strings.update(double_quote_matches)
    return sorted(list(extracted_strings))


def update_js_translations_file(new_strings):
    if TRANSLATIONS_FILE.exists():
        with open(TRANSLATIONS_FILE, "r", encoding="utf-8") as f:
            translations_data = json.load(f)
    else:
        translations_data = {"en": {}, "ja": {}}

    updated = False
    for lang in ["en", "ja"]:
        for s in new_strings:
            if s not in translations_data[lang]:
                translations_data[lang][s] = s  # Use English as placeholder
                updated = True

    if updated:
        with open(TRANSLATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(translations_data, f, ensure_ascii=False, indent=4)
        print(f"Updated {TRANSLATIONS_FILE} with new JavaScript strings.")
    else:
        print(f"No new JavaScript strings to add to {TRANSLATIONS_FILE}.")


if __name__ == "__main__":
    print("Extracting JavaScript strings...")
    strings = extract_js_strings()
    update_js_translations_file(strings)
