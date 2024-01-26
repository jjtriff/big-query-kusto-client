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
- Compile and publish using
`$ poetry publish --build`

