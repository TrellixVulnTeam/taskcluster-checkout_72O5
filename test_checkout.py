import checkout
import shutil
import os
import contextlib
import mock
import urllib2
import sys

from nose.tools import eq_
from testfixtures import tempdir

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


@contextlib.contextmanager
def mocked_urllib2(data, no_size=False, exp_size=4096, exp_token=None):
    with mock.patch('urllib2.urlopen') as urlopen:
        def fake_read(url, size):
            eq_(size, exp_size)
            remaining = data[url]
            rv, remaining = remaining[:size], remaining[size:]
            data[url] = remaining
            return rv

        def replacement(req):
            url = req.get_full_url()
            if url not in data:
                raise urllib2.URLError("bogus url")
            m = mock.Mock(name='Response')
            if no_size:
                def mocked_read():
                    return fake_read(url, exp_size)
                m.read = mocked_read
            else:
                m.read = lambda size: fake_read(url, size)
            return m
        urlopen.side_effect = replacement
        yield


def call_main(*args):
    try:
        old_stderr = sys.stderr
        sys.stderr = sys.stdout
        try:
            return checkout.main(list(args))
        except SystemExit, e:
            return "exit %d" % e.code
    finally:
        sys.stderr = old_stderr

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
    output = os.path.join(tmpdir.path, 'file')
    with mocked_urllib2({'http://foo.bar/baz': 'abcd'}):
        checkout.download_file('http://foo.bar/baz', output)
        eq_(open(output).read(), 'abcd')


@tempdir()
def test_download_file_invalid_url(tmpdir):
    """ download should fail when the url is invalid"""
    output = os.path.join(tmpdir.path, 'file')
    with mocked_urllib2({'http://foo.bar/baz': 'abcd'}):
        assert not checkout.download_file('http://foo.bar/qux', output)



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
    """ this should fail since the remote is invalid."""
    latest_artifact_url = checkout.urljoin(checkout.TC_INDEX, 'task', 'bar')
    with mocked_urllib2({latest_artifact_url: '{"taskId":"baz"}'}, no_size=True):
        assert not checkout.clone_from_cache('foo', 'bar', None, tmpdir.path)


@tempdir()
def test_clone_from_cache_bad_namespace(tmpdir):
    """ this should fail since the namespace is invalid."""
    latest_artifact_url = checkout.urljoin(checkout.TC_INDEX, 'task', 'bar')
    with mocked_urllib2({'http://bad.url/': '{"taskId":"baz"}'}, no_size=True):
        assert not checkout.clone_from_cache('foo', 'bar', None, tmpdir.path)


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
    with mock.patch('checkout.clone_from_cache') as mocked:
        assert checkout.clone(TEST_HG_REPO_REMOTE, output)
        assert not mocked.called


@tempdir()
def test_clone_no_cache(tmpdir):
    """ cloning operation should not call any cloning operations and succeed"""

    def mocked_cache(*args):
        return False

    local_remote = setup_hg_repo(tmpdir.path)
    output = os.path.join(tmpdir.path, 'cloned_repo')
    with mock.patch('checkout.clone_from_cache', side_effect=mocked_cache):
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


def test_main_no_command():
    eq_(call_main(), "exit 2")


def test_main_checkout():
    def do_nothing(*args):
        pass

    with mock.patch('checkout.checkout', side_effect=do_nothing) as mocked:
        call_main('dir', 'remote')
        mocked.assert_called_with('dir', 'remote', None, None)
