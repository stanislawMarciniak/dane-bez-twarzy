#!/usr/bin/env python3
"""
Script to extract word-label pairs between anonymized and original text files.
Compares orig.txt (with placeholders like [city]) to anonymized.txt (with real values)
and outputs the mappings to a JSON file.

Note: Despite the file naming:
- orig.txt contains PLACEHOLDERS like [name], [city], [phone]
- anonymized.txt contains REAL VALUES like "Apolonia Kościesza", "Nowa Ruda"
"""

import json
import re
from collections import defaultdict
from pathlib import Path


def extract_label_pairs(placeholder_file: Path, values_file: Path) -> dict[str, list[str]]:
    """
    Extract label-value pairs by comparing placeholder and values files.
    
    Returns a dict where keys are labels (e.g., 'city') and values are lists
    of unique real values found for that label.
    """
    label_pairs = defaultdict(set)
    
    # Pattern to match placeholders like [city], [name], [phone], etc.
    placeholder_pattern = re.compile(r'\[([a-zA-Z0-9_-]+)\]')
    
    with open(placeholder_file, 'r', encoding='utf-8') as pf, \
         open(values_file, 'r', encoding='utf-8') as vf:
        
        for line_num, (placeholder_line, values_line) in enumerate(zip(pf, vf), 1):
            placeholder_line = placeholder_line.strip()
            values_line = values_line.strip()
            
            # Find all placeholders in the placeholder line
            placeholders = list(placeholder_pattern.finditer(placeholder_line))
            
            if not placeholders:
                continue
            
            # Build a regex pattern from the placeholder line to extract values
            regex_pattern = placeholder_line
            
            # Sort placeholders by position (reverse order) to replace from end to start
            placeholders_sorted = sorted(placeholders, key=lambda m: m.start(), reverse=True)
            
            # Track placeholder labels in order
            labels_in_order = []
            
            # Build the pattern by replacing placeholders with capture groups
            for match in placeholders_sorted:
                label = match.group(1)
                start, end = match.span()
                
                # Replace placeholder with a marker
                regex_pattern = regex_pattern[:start] + '<<<PLACEHOLDER>>>' + regex_pattern[end:]
                labels_in_order.insert(0, label)  # Insert at beginning since we're going reverse
            
            # Escape the pattern parts (everything except our markers)
            parts = regex_pattern.split('<<<PLACEHOLDER>>>')
            escaped_parts = [re.escape(p) for p in parts]
            
            # Join with capture groups - use .+? for non-greedy matching
            regex_pattern = r'(.+?)'.join(escaped_parts)
            
            # Make the last capture group greedy if it's at the end
            if regex_pattern.endswith(r'(.+?)'):
                regex_pattern = regex_pattern[:-5] + r'(.+)'
            
            try:
                result = re.match(regex_pattern, values_line, re.DOTALL)
                if result:
                    for i, label in enumerate(labels_in_order):
                        if i < len(result.groups()):
                            value = result.group(i + 1)
                            if value:
                                label_pairs[label].add(value.strip())
            except re.error:
                # Skip lines that can't be parsed with regex
                pass
    
    # Convert sets to sorted lists for JSON serialization
    return {label: sorted(list(values)) for label, values in sorted(label_pairs.items())}


def create_flat_pairs(label_dict: dict) -> list[dict]:
    """Create a flat list of label-value pairs for alternative output format."""
    pairs = []
    for label, values in label_dict.items():
        for value in values:
            pairs.append({
                "label": f"[{label}]",
                "value": value
            })
    return pairs


def main():
    # File paths
    # Note: orig.txt has placeholders, anonymized.txt has real values
    base_path = Path(__file__).parent / "nask_train"
    placeholder_file = base_path / "orig.txt"      # Contains [name], [city], etc.
    values_file = base_path / "anonymized.txt"     # Contains real values
    
    print(f"Reading placeholder file: {placeholder_file}")
    print(f"Reading values file: {values_file}")
    
    # Extract label pairs
    label_pairs = extract_label_pairs(placeholder_file, values_file)
    
    # Create output structures
    output = {
        "summary": {
            "total_labels": len(label_pairs),
            "labels_found": list(label_pairs.keys()),
            "value_counts": {label: len(values) for label, values in label_pairs.items()}
        },
        "mappings": label_pairs,
        "pairs": create_flat_pairs(label_pairs)
    }
    
    # Write to JSON file
    output_file = base_path.parent / "label_mappings.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ Output written to: {output_file}")
    print(f"\n--- Summary ---")
    print(f"Total label types found: {len(label_pairs)}")
    for label, values in sorted(label_pairs.items()):
        print(f"  [{label}]: {len(values)} unique values")
    
    # Show some examples
    print(f"\n--- Sample mappings (first 3 values per label) ---")
    for label, values in list(label_pairs.items())[:15]:
        sample_values = values[:3]
        more = f" ... (+{len(values)-3} more)" if len(values) > 3 else ""
        print(f"  [{label}]: {sample_values}{more}")


if __name__ == "__main__":
    main()
