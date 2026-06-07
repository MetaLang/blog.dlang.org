import os
from pathlib import Path
import re
import sys

try:
    filename = os.environ['POST_FILENAME']
except KeyError as e:
    print(f"Error: Missing expected environment variable {e}")
    sys.exit(1)

file_path = f"_posts/live/{filename}"

try:
	with open(file_path, 'r', encoding='utf-8') as file:
		content = file.readlines()
except FileNotFoundError:
    print(f"Error: Could not find file at {file_path}")
    sys.exit(1)

# Regex pattern explanation:
# (?<!`)   : Negative lookbehind - ensures the match doesn't start directly after a backtick
# `        : Matches a single starting backtick
# [^`]+    : Matches one or more characters that are NOT backticks
# `        : Matches a single closing backtick
# (?!`)    : Negative lookahead - ensures the match isn't immediately followed by a backtick
inline_code_pattern = re.compile(r'(?<!`)`[^`]+`(?!`)')
new_content = []
in_code_block = False

for line in content:
	if line.strip().startswith("```"):
		if in_code_block:
			# We're already in a code block and have reached the end
			in_code_block = False
			new_content.append(line)
			new_content.append("{% endraw %}\n")
		else:
			in_code_block = True
			new_content.append("{% raw %}\n")
			new_content.append(line)
	else:
		if not in_code_block:
			line = inline_code_pattern.sub(lambda match: f"{{% raw %}}{match.group(0)}{{% endraw %}}", line)
		new_content.append(line)

with open(file_path, 'w', encoding='utf-8') as file:
	file.write("".join(new_content))

print(f"Successfully added Liquid raw tags around code blocks in {file_path}")