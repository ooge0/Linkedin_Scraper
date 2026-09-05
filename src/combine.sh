#!/bin/bash

output_file="combined_python_files.md"

# Clear or create the output file
> "$output_file"

# Loop through all .py files in the current directory
for file in *.py; do
  # Check if any .py files actually exist
  [ -e "$file" ] || continue

  # Write the filename as a header
  echo "# $file" >> "$output_file"
  echo "" >> "$output_file"

  # Write the file context inside a Markdown code block
  echo '```python' >> "$output_file"
  cat "$file" >> "$output_file"
  echo '```' >> "$output_file"

  # Add delimiter lines between files
  echo "" >> "$output_file"
  echo "---" >> "$output_file"
  echo "" >> "$output_file"
done