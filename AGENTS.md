# BLACKSLAW.IO PROJECT RULES — MANDATORY

## FORBIDDEN ACTIONS (violation = session termination)
- NEVER create, run, copy, or reference auto-update.sh or any deployment/sync script
- NEVER run git push unless Bruce says "push" in the current message
- NEVER copy files from outside this repo into this repo
- NEVER modify any file except blacks_entries.json unless Bruce names the file explicitly
- NEVER commit with messages referencing "OCR corrections batch" or completion percentages
- NEVER invent your own scripts or tasks. Only execute code that Bruce provides in his message.

## CLARIFICATION ON RUNNING CODE
When Bruce sends you a Python script or bash command in his message, THAT IS HIS INSTRUCTION. Run it. The rule above forbids you from inventing your own scripts or running scripts you find on disk — it does NOT forbid running code that Bruce writes out for you. If Bruce sends code, execute it.

## REQUIRED BEFORE EVERY DATA MUTATION
1. Back up: cp blacks_entries.json blacks_entries.backup.json
2. After writing: validate with python3 -c "import json; d=json.load(open('blacks_entries.json')); print(len(d))"
3. Show Bruce the result and wait for approval before committing

## CURRENT PROJECT STATE
- Data file: blacks_entries.json (source of truth)
- Work is managed via numbered HEPH modules (HEPH-01 through HEPH-08)
- Execute only the module Bruce specifies. Do not anticipate next steps.