import re
import os
import sys

try:
    slug = os.environ['POST_SLUG']
    filename = os.environ['POST_FILENAME']
except KeyError as e:
    print(f"Error: Missing expected environment variable {e}")
    sys.exit(1)

file_path = f"_posts/live/{filename}"

try:
    with open(file_path, 'r', encoding='utf-8', newline=None) as f:
        content = f.read()
except FileNotFoundError:
    print(f"Error: Could not find file at {file_path}")
    sys.exit(1)

# Matches `![Any Alt Text](` only if it is NOT followed by http or /
pattern = r'(!\[[^\]]*\]\()(?!http|/)'

# \g<1> returns the exact matched string (e.g., `![My Alt Text](`)
# We then immediately append the absolute path. The original filename remains untouched.
replacement = rf'\g<1>/assets/images/{slug}/'

new_content = re.sub(pattern, replacement, content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f"Successfully rewrote local image links to absolute links in {file_path}")