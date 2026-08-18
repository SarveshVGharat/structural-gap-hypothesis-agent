# Release TODO

Remaining decisions before public GitHub release:

- Fill in final `CITATION.cff` metadata, including author list, paper title, repository URL, DOI if assigned, venue if known, and arXiv identifier.
- Decide whether optional dependency groups should stay broad or be split further, especially `baselines`, `retrieval`, and `serve`.
- Document third-party baseline reproduction with upstream repository URLs, commit hashes, licenses, and user-provided model/checkpoint requirements:
  - AI-Scientist-v2 upstream repository URL, commit hash, license, expected install command, and any required local patch.
  - MOOSE-Star upstream repository or package source, public model identifier/path, license, hardware expectation, and validation-only command.
