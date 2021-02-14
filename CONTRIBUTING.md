# Contributing to _backupbrace_

First off, thank you for taking the time to contribute!

My experience with writing in Python is limited. As such, I welcome constructive criticism and
improvements to the code to make it become more in line with best practices for Python.

The following is a set of guidelines for contributing to _backupbrace_. These are mostly guidelines,
not rules. Use your best judgment, and feel free to propose changes to this document in a pull
request.

## Code of Conduct

This project and everyone participating in it is governed by a
[code of conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.
Please report unacceptable behavior to github@closingbrace.nl.

## Coding Conventions

### Python Styleguide

* Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)
* Write docstrings for your classes and functions. In the docstring, write what the class or
  function is about, when it should be used and how it should be used, but leave out details that
  are really obvious. Don't go into the details of how the class or function is implemented, unless
  this is necessary for understanding when or how to use it.
* Try to keep your functions short and have them do only one thing. As a rule of thumb, the function
  should fit on the screen easily (excluding the docstring).

### Git Commits

There is a lot written about what makes a commit a good commit. See for example Chris Beams' article
[How to Write a Git Commit Message](https://chris.beams.io/posts/git-commit/) and Ruan Brandão's
article [How to make good Git commits](https://dev.to/ruanbrandao/how-to-make-good-git-commits-256k).
Although I find the rule that the summary line should be 50 characters or less sometimes to
restrictive, in general use the advice given in these articles as guidelines for your commits.

The most important rules are:
* Use the imperative mood in your commit message (write "Add feature", not "Adds feature" or "Added
  feature")
* Keep the summary short, elaborate in the body of the commit message when necessary.
* Make each commit introduce or change one feature or bugfix, and one feature or bugfix only.
* Don't add commits that fix bugs you introduced in previous commits. Fix the bugs in those previous
  commits themselves.
