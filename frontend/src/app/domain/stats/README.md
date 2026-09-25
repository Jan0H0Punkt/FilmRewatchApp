# `domain/stats/` — viewing statistics

Data access and mapping for `GET /stats`. Every number is computed by the
backend (`backend/app/stats/algorithm.py`); this layer only renames fields and
turns a year block's month buckets (`"1"`…`"12"`) into `Jan`…`Dec`.
