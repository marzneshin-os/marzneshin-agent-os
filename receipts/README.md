# Receipts Directory
This directory holds the receipt chain for the orchestration system.
Each receipt is a JSON file with a `prev_receipt_hash` field linking to the previous receipt.
Receipts are append-only and must never be modified after creation.
Schema: `{YYYY-MM-DD}-{HHMMSS}-{id}.json`
