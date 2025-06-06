# Contributing - WIP - aka Notes to self about how to do things

## Use TDD
- For anything that needs improvement create a unit test first
- After the test fails, go ahead and implement the solution

## Branch Model
- feature branches
- 1 main branch
- merging by rebasing, so, short-lived branches
- Only push and PR the code, not the binaries

## Releasing
1. Update the version in `pyproject.toml`
2. Commit and push your changes
3. Create a new release on GitHub:
   - Go to the repository on GitHub
   - Click on "Releases" > "Create a new release"
   - Tag version should follow semantic versioning (e.g., v0.4.1)
   - Set release title and describe the changes
   - Click "Publish release"
4. The GitHub Actions workflow will automatically:
   - Build the package
   - Publish it to PyPI

Note: This requires a PyPI API token to be set as a GitHub secret named `PYPI_API_TOKEN`.
