"""Process-local resource admission. Run one backend worker."""
benchmark_active = False
model_operations: set[str] = set()
