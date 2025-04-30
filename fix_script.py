#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re

# Read the file
with open('/Users/riccardo/CRV_bot/bot_fixed.py', 'r') as file:
    content = file.read()

# Define the patterns to fix
patterns = [
    (
        'row = [InlineKeyboardButton(squadre[i + 1], callback_data=squadre[i + 1]))\n                keyboard.append(row\n                if i + 1 < len(squadre):\n                    row.append(InlineKeyboardButton(squadre[i], callback_data=squadre[i]))',
        'row = [InlineKeyboardButton(squadre[i], callback_data=squadre[i])]\n                if i + 1 < len(squadre):\n                    row.append(InlineKeyboardButton(squadre[i + 1], callback_data=squadre[i + 1]))\n                keyboard.append(row)'
    ),
    (
        'row = [InlineKeyboardButton(squadre[i + 1], callback_data=squadre[i + 1]))\n            keyboard.append(row\n            if i + 1 < len(squadre):\n                row.append(InlineKeyboardButton(squadre[i], callback_data=squadre[i]))',
        'row = [InlineKeyboardButton(squadre[i], callback_data=squadre[i])]\n            if i + 1 < len(squadre):\n                row.append(InlineKeyboardButton(squadre[i + 1], callback_data=squadre[i + 1]))\n            keyboard.append(row)'
    ),
    (
        'row = [InlineKeyboardButton(squadre[i + 1], callback_data=squadre[i + 1]))\n                    keyboard.append(row\n                    if i + 1 < len(squadre):\n                        row.append(InlineKeyboardButton(squadre[i], callback_data=squadre[i]))',
        'row = [InlineKeyboardButton(squadre[i], callback_data=squadre[i])]\n                    if i + 1 < len(squadre):\n                        row.append(InlineKeyboardButton(squadre[i + 1], callback_data=squadre[i + 1]))\n                    keyboard.append(row)'
    )
]

# Apply all the fixes
fixed_content = content
for pattern, replacement in patterns:
    fixed_content = fixed_content.replace(pattern, replacement)

# Fix indentation issues
# Pattern per trovare il ciclo for con indentazione errata
pattern = re.compile(
    r'([ \t]+)for i in range\(0, len\(squadre\), 2\):\n'
    r'([ \t]+)row = \[InlineKeyboardButton\(squadre\[i\], callback_data=squadre\[i\]\)\]\n'
    r'([ \t]+)if i \+ 1 < len\(squadre\):\n'
    r'([ \t]+)row\.append\(InlineKeyboardButton\(squadre\[i \+ 1\], callback_data=squadre\[i \+ 1\]\)\)\n'
    r'([ \t]+)keyboard\.append\(row\)'
)

# Funzione di sostituzione che corregge l'indentazione
def fix_match(match):
    base_indent = match.group(1)
    row_indent = match.group(2)
    
    return (
        f"{base_indent}for i in range(0, len(squadre), 2):\n"
        f"{row_indent}row = [InlineKeyboardButton(squadre[i], callback_data=squadre[i])]\n"
        f"{row_indent}if i + 1 < len(squadre):\n"
        f"{row_indent}    row.append(InlineKeyboardButton(squadre[i + 1], callback_data=squadre[i + 1]))\n"
        f"{row_indent}keyboard.append(row)"
    )

# Applica la correzione
fixed_content = pattern.sub(fix_match, fixed_content)

# Write the fixed content back to the file
with open('/Users/riccardo/CRV_bot/bot_fixed_corrected.py', 'w') as file:
    file.write(fixed_content)

print("File fixed successfully!")