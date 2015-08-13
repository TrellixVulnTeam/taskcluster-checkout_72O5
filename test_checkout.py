import checkout
import shutil
import os

from nose.tools import eq_
from testfixtures import tempdir
from mock import patch

TEST_HG_REPO_REMOTE = 'https://bitbucket.org/acmiyaguchi/tc-hg-testing'
TEST_HG_REPO_ALIAS = 'bitbucket.org/acmiyaguchi/tc-hg-testing'
TEST_HG_REPO_TAR = 'test-repo.tar.gz'


###############################################################################
# Test Helpers
###############################################################################

def setup_local_cache(topdir):
    """ copy test-repo.tar.gz to a temp cache folder"""
    file_path = os.path.join(topdir, 'clones', TEST_HG_REPO_TAR)
    if not os.path.exists(file_path):
        os.makedirs(os.path.dirname(file_path))
        shutil.copyfile(TEST_HG_REPO_TAR, file_path)


def setup_hg_repo(topdir, dest='dest'):
    """ setup a hg repository in the given folder using clone_from_cache"""
    setup_local_cache(topdir)
    output = os.path.join(topdir, dest)
    checkout.clone_from_cache(TEST_HG_REPO_TAR.split('.')[0], None, output, cache_dir=topdir)
    return output


def set_hg_repo_path(repo, remote):
    try:
        with open(os.path.join(repo, '.hg', 'hgrc'), 'w') as f:
            f.write('[paths]\ndefault={}'.format(remote))
    except:
        return False

    return True


###############################################################################
# Unit and Coverage Tests
###############################################################################

def test_alias():
    """ resulting alias should be the url stripped of the protocol"""
    test_input = 'https://foo.org/bar'
    expected = 'foo.org/bar'
    actual = checkout.get_alias(test_input)
    eq_(expected, actual)


def test_urljoin_no_slash():
    """ arbitrary number of elements should be joined with a forward slash"""
    test_input = ['foo', 'bar', 'baz', 'qux']
    expected = 'foo/bar/baz/qux'
    actual = checkout.urljoin(*test_input)
    eq_(expected, actual)


def test_urljoin_right_slashes():
    """ arbitrary number of elements followed by a slash should be joined with a single slash"""
    test_input = ['foo/', 'bar', 'baz/', 'qux']
    expected = 'foo/bar/baz/qux'
    actual = checkout.urljoin(*test_input)
    eq_(expected, actual)


@tempdir()
def test_download_file(tmpdir):
    """ download a file to disk, assert that location exists on disk"""
    pass


@tempdir()
def test_download_file_invalid_url(tmpdir):
    """ download should fail when the url is invalid"""
    pass


@tempdir()
def test_clone_from_cache_local(tmpdir):
    """ when a cached version already exists on disk, this uses a version and should succeed"""
    setup_local_cache(tmpdir.path)
    output = os.path.join(tmpdir.path, 'dest')
    assert checkout.clone_from_cache(TEST_HG_REPO_TAR.split('.')[0], None, output,
                                     cache_dir=tmpdir.path)
    assert os.path.exists(os.path.join(output, '.hg', 'hgrc'))


@tempdir()
def test_clone_from_cache_remote(tmpdir):
    """ this downloads a file from a remote cache and extracts the repository."""
    pass


@tempdir()
def test_clone_from_cache_bad_remote(tmpdir):
    """ should fail when given an invalid alias"""
    pass


@tempdir()
def test_path_is_hg_repo(tmpdir):
    """ should succeed when a path is a valid mercurial repository"""
    output = setup_hg_repo(tmpdir.path)
    assert checkout.path_is_hg_repo(output, checkout.get_alias(TEST_HG_REPO_REMOTE))


@tempdir()
def test_path_is_invalid_hg_repo(tmpdir):
    """ when the hgrc does not contain the remote alias, should return false"""
    output = setup_hg_repo(tmpdir.path)
    assert not checkout.path_is_hg_repo(output, checkout.get_alias(
        'https://hg.mozilla.org/mozilla-central'))


@tempdir()
def test_path_is_not_hg_repo(tmpdir):
    """ when path is not a mercurial repository, this should return false"""
    assert not checkout.path_is_hg_repo(tmpdir.path, None)


@tempdir()
def test_invalid_revision(tmpdir):
    """ get a revision from an invalid repo"""
    eq_(checkout.revision(tmpdir.path), None)


@tempdir()
def test_clone_already_exists(tmpdir):
    """ cloning operation should not call any cloning operations and succeed"""
    output = setup_hg_repo(tmpdir.path)
    with patch('checkout.clone_from_cache') as mocked:
        assert checkout.clone(TEST_HG_REPO_REMOTE, output)
        assert not mocked.called


@tempdir()
def test_clone_no_cache(tmpdir):
    """ cloning operation should not call any cloning operations and succeed"""

    def mocked_cache(*args):
        return False

    local_remote = setup_hg_repo(tmpdir.path)
    output = os.path.join(tmpdir.path, 'cloned_repo')
    with patch('checkout.clone_from_cache', side_effect=mocked_cache):
        assert checkout.clone(local_remote, output)
        assert os.path.exists(os.path.join(output, '.hg', 'hgrc'))


@tempdir()
def test_clone_already_invalid_vcs(tmpdir):
    """ clone operation should not succeed when the folder is not a repo"""
    assert not checkout.clone(TEST_HG_REPO_REMOTE, tmpdir.path)


@tempdir()
def test_checkout_default(tmpdir):
    """ checkout operation should succeed, and point to the latest revision"""
    remote = setup_hg_repo(tmpdir.path, 'remote')
    output = setup_hg_repo(tmpdir.path)
    set_hg_repo_path(output, remote)
    checkout.checkout(output, remote)
    eq_(checkout.revision(output), '176e98c1d359')


@tempdir()
def test_checkout_revision(tmpdir):
    """ checkout operation should succeed and point to some revision"""
    remote = setup_hg_repo(tmpdir.path, 'remote')
    output = setup_hg_repo(tmpdir.path)
    set_hg_repo_path(output, remote)
    checkout.checkout(output, remote, head_rev='123df26ca0f5')
    eq_(checkout.revision(output), '123df26ca0f5')

