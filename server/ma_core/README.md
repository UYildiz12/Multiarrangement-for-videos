# ma_core

`ma_core` contains the lightweight algorithm subset used by the hosted FastAPI backend.
It keeps the scheduling and fusion logic available without depending on the desktop
UI stack.

Included modules:

- `batch_generator.py`: fixed-batch generation helpers
- `lift_weakest.py`: adaptive LTW scheduler and evidence updates
- `setcover_fusion.py`: set-cover fusion utilities
- `optimize_cover_pure.py`: compatibility wrapper for packaged optimizers
