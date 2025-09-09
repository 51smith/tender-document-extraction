### Why Ruff reports RET505
Ruff’s RET505 (from the flake8-return rules) flags code where an `else` (or `elif`) directly follows a branch that unconditionally exits the function (e.g., `return`, `raise`, `break`, `continue`). Once you return, the function cannot continue into the following code path, so the `else` is redundant and can be safely removed by de-indenting its body.

This is purely a readability/style rule. It doesn’t change behavior if the logic is preserved when you remove the `else` and keep the early `return`.

### Why your tests might fail when you “remove else”
The failures usually happen not because removing the `else` is wrong, but because the refactor accidentally changed control flow. Two common pitfalls:

- You removed the `else` but also (perhaps inadvertently) removed or moved the early `return`, causing the function to “fall through” to the next block (e.g., the single-document path) instead of exiting early.
- You removed the `else` but didn’t de-indent its contents correctly, changing which code is executed in some cases.

In async code, `await` doesn’t change any of this: `return` still exits the function immediately (after the `finally` block runs). So the correct refactor should keep the same early exits and simply drop the redundant `else`.

### Concrete example from your file (around line 832)
Current (trimmed to the relevant part):

- If documents are available, you do work and `return` at line 832.
- Else, you update status to FAILED and `return` an error at lines 835–841.

Ruff flags this because the `else` after a guaranteed `return` is unnecessary.

### Safe refactor that satisfies RET505 and preserves behavior
Here’s how to rewrite the block with guard clauses and early returns. Behavior is unchanged, and tests should pass as long as you preserve the early returns.

```python
# Batch request - process all documents together in single API call
batch_request = BatchExtractionRequest(**request_data)
await job_manager.update_job_status(job_id, ExtractionStatus.PROCESSING, 10.0)

available_documents = {
    filename: content
    for filename, content in file_contents.items()
    if content is not None
}

missing_files = {doc.filename for doc in batch_request.documents} - set(available_documents.keys())
if missing_files:
    logger.warning(f"Missing file contents for: {missing_files}")

# Guard clause: no docs available -> fail and exit
if not available_documents:
    await job_manager.update_job_status(
        job_id,
        ExtractionStatus.FAILED,
        progress=100.0,
        error_message="No documents available for processing",
    )
    return {"error": "No documents available for processing"}

# Normal path
await job_manager.update_job_status(job_id, ExtractionStatus.PROCESSING, 50.0)
result = await service._process_multiple_documents(available_documents, batch_request)
await job_manager.update_job_status(
    job_id, ExtractionStatus.COMPLETED, progress=100.0, result=[result]
)
return {"results": [result.dict() if hasattr(result, "dict") else result]}
```

Note the key points:
- We replaced the `if available_documents: ... return ... else: ... return ...` with a guard clause: `if not available_documents: ... return`, followed by the main path.
- There is still an early `return` in the error path. If that return is removed, the function will fall through to the single-document branch and your error-handling tests will fail.

### A pattern for graceful error handling (without the return/else anti-pattern)
A few practices that keep code clean and robust:

- Use guard clauses: Fail fast, return/raise early for invalid or missing inputs; then write the main success path without extra nesting.
- Centralize exception translation: If you’re already using `_handle_job_error`, keep `try/except` narrow and let that function update job status and transform exceptions into domain errors/messages. Avoid spreading many tiny `try/except` blocks.
- Prefer raising domain-specific exceptions at boundaries and handle them at a single layer (e.g., job-processing boundary) when appropriate. In your case, because the API returns dicts, returning an error dict is fine—just be consistent.
- Keep `finally` blocks for cleanup; they will run whether you `return` or raise. So early returns do not skip cleanup.

### If you must keep the same shape and still silence Ruff
Refactoring as above is best. But if you need to keep the current structure temporarily, you can scope-ignore the rule:

- Inline: `# noqa: RET505` at the end of the relevant `else:` line.
- Or configure in pyproject.toml to ignore RET505 for this file or globally (not recommended globally):

```toml
[tool.ruff.lint]
ignore = ["RET505"]  # global
# or
[tool.ruff.lint.per-file-ignores]
"app/services/extraction_worker.py" = ["RET505"]
```

### Summary
- Ruff is correct: `else` after an unconditional `return` is redundant (RET505).
- Your test failures likely came from accidentally removing the early `return` (or mis-indenting) when you dropped the `else`.
- Use guard clauses: return on the error condition first, then proceed with the normal path; this removes the `else` and keeps behavior identical.
- Async doesn’t change the semantics: `return` still exits; `finally` still runs.
- If needed, silence RET505 locally, but the refactor above is the idiomatic fix.
