import csv
from collections import defaultdict
import sys
import csv
from collections import defaultdict

# Increase field size limit
csv.field_size_limit(2**31-1)

input_file = "my_meta_tags.csv"
output_file = "my_meta_tags_formatted.csv"

# Store data in a dict: domain → { tag_name: tag_content }
domain_data = defaultdict(dict)

with open(input_file, "r", encoding="utf-8") as f:
    reader = csv.reader(f)
    next(reader)
    current_domain = None
    for row in reader:
        domain, tag_name, tag_content = row
        if tag_name == "---":
            current_domain = domain
        else:
            domain_data[current_domain][tag_name] = tag_content

# Build all possible columns from tags
all_tags = set()
for tags in domain_data.values():
    all_tags.update(tags.keys())

# Make consistent column order
final_headers = ["Domain"] + sorted(all_tags)

# Write the formatted CSV
with open(output_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=final_headers)
    writer.writeheader()
    for domain, tags in domain_data.items():
        row = {"Domain": domain}
        row.update(tags)
        writer.writerow(row)

print("✅ CSV converted to structured format:", output_file)
