You are assisting with development of the 'sudoblark.ai.bookshelf-demo' project.
This project is a fully local, offline-friendly AI ETL pipeline.

Your goals:
1. Help implement a local event-driven workflow:
   - Monitor the data/raw directory for new image files.
   - Pass images through a metadata extractor.
   - Produce structured metadata output.
   - Write Parquet files into the data/processed directory.

2. Generate Python code following these principles:
   - Keep modules simple and single-purpose (extractor, watcher, parquet writer).
   - Use pandas + pyarrow for Parquet generation.
   - Use watchdog for filesystem events.
   - Avoid cloud dependencies; everything is local.
   - Leave integration points for a Copilot Studio agent, but don’t require them.

3. Maintain clear architecture boundaries:
   - The processor/ folder contains all backend logic.
   - The data/raw and data/processed folders act as storage.
   - Copilot extraction will be implemented separately.

4. Code quality expectations:
   - Prefer small functions.
   - Prefer explicit paths over magic values.
   - Include helpful comments where a future Copilot API call will be inserted.
   - Suggest improvements only if they serve clarity or maintainability.

5. Do not generate Terraform, GitHub Actions, or cloud infrastructure code unless explicitly asked.

Your default behaviour:
- When creating or modifying Python files, follow the structure established above.
- When generating file watchers, assume local execution only.
- When generating extractors, return placeholder metadata unless the user requests Copilot integration.
- When generating Parquet writers, always include timestamped filenames.

If uncertain, ask clarifying questions before generating code.