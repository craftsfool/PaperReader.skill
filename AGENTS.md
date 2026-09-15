# Repository Guidelines

This repository distributes the PaperReader translation skill for Codex.

## Structure

- `skills/paperreader-translate/SKILL.md`: workflow entry point.
- `skills/paperreader-translate/scripts`: standalone local document helpers.
- `skills/paperreader-translate/references`: translation and parser guidance.
- `tests/skill`: standard-library unittest coverage.

## Development

Use Python 3.10 or newer and four-space indentation. The helpers must run without the original PaperReader backend or an LLM API key. PDF tests require the skill's `scripts/requirements.txt` installed in a virtual environment.

Run `python -m unittest discover -s tests/skill -v` for helper changes. Check that protected formulas and references survive exactly, missing translations fail export, and source files remain untouched. Validate compiled PDF changes by rendering and inspecting the output.

Keep temporary papers, model weights, virtual environments and generated deliverables outside the repository. Preserve upstream attribution and distinguish tested adapters from full parser inference validation.

Use concise imperative commit messages. Do not add generation or co-author signatures. Publish only to the explicitly authorized repository.
