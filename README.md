TaskCluster Checkout (tc-checkout)
==================================

This is a python client to access cached mercurial repositories served by TaskCluster.

### Running taskcluster-checkout

To run the tool for development, pip install the requirements into your virtualenv:

    pip install -e .[test]

The `[test]` installs the requirements for testing as well.
Omit this if you won't be running tests.


### Usage
    tc-checkout [-h] directory baseUrl [headUrl] [headRev] [headRef]

    positional arguments:
      directory   Target directory which to clone and update
      baseUrl     Base repository to clone
      headUrl     Head url to fetch changes from. If this value is not given
                  baseUrl is used.
      headRev     Revision/changeset to pull from the repository. If not given
                  this defaults to the "tip"/"master" of the default branch.
      headRef     Reference on head to fetch this should usually be the same value
                  as headRev primarily this may be needed for cases where you are
                  fetching a revision from a git branch but must fetch the
                  reference and then proceed to checkout the particular revision
                  you want (git generally does not support pulling specific
                  revisions only references). If not given defaults to headRev.
                  NOTE: This option is not currently supported and is ignored.

Run `tc-checkout --help` for the help information.
