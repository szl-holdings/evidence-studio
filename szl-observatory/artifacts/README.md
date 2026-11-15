# Snapshot artifact contract

The production collector must write a new immutable JSON snapshot here (or to the
configured Hugging Face dataset) with `schema_version=szl.observatory.snapshot/v1`.

The checked-in local baseline is generated with:

```bash
PYTHONPATH=src python -m szl_observatory.cli export artifacts/seed_snapshot.json
PYTHONPATH=src python hf_templates/kernel.py --snapshot artifacts/seed_snapshot.json
```

Seed values are explicitly labelled `estimated` where they originate from operating
notes. They must be reconciled with live provider exports before being presented as
current analytics.
