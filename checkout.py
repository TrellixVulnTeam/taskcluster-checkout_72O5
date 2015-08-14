# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import hashlib
import urlparse
import urllib2
import argparse
import logging
import json
import tarfile
import shutil
import sys
import tempfile

import os
import hglib

TC_NAMESPACE = 'tc-vcs.v1.clones'
TC_QUEUE = 'https://queue.taskcluster.net/v1'
TC_INDEX = 'https://index.taskcluster.net/v1'
CACHE_DIR = os.path.join(os.path.expanduser('~'), '.tc-vcs')

log = logging.getLogger(__name__)


def get_alias(url):
    """
    :param url: url of the repository
    :return: a string that is the url that has been stripped of the protocol
    """
    o = urlparse.urlparse(url)
    return o.netloc + o.path


def urljoin(*args):
    """
    Joins together a list of strings that make up a url, by stripping the right-most slash
    :param args: a list of strings making up an url
    :return: a joined url
    """
    return "/".join(map(lambda x: str(x).rstrip('/'), args))


def download_file(url, dest, grabchunk=1024 * 4):
    """
    Download a file to disk
    :param url: Url of item to download
    :param dest: path to save the file
    :param grabchunk: chunk size to download file in
    """
    path = None
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, os.path.basename(dest))
    try:
        req = urllib2.Request(url)
        f = urllib2.urlopen(req)
        log.debug("opened {} for reading".format(url))
        with open(temp_path, 'wb') as out:
            k = True
            size = 0
            while k:
                indata = f.read(grabchunk)
                out.write(indata)
                size += len(indata)
                if indata == '':
                    k = False
            log.info("file {} downloaded from {}".format(dest, os.path.basename(url)))
        shutil.move(temp_path, dest)
        path = dest
    except (urllib2.URLError, urllib2.HTTPError, ValueError) as e:
        log.info("... failed to download {} from {}".format(dest, os.path.basename(url)))
        log.debug("{}".format(e))
    except IOError:  # pragma: no cover
        log.info("failed to write to file for {}".format(dest), exc_info=True)

    shutil.rmtree(temp_dir)
    return path


def get_latest_taskid(namespace):
    """ get the taskid of the latest artifact in a namespace"""
    latest_artifact_url = urljoin(TC_INDEX, 'task', namespace)
    try:
        req = urllib2.Request(latest_artifact_url)
        resp = urllib2.urlopen(req)
        task = json.loads(resp.read())
    except (urllib2.URLError, urllib2.HTTPError, ValueError) as e:
        log.info("unable to retrieve task from {}".format(latest_artifact_url))
        log.debug("{}".format(e))
        return None
    return task['taskId']


def clone_from_cache(alias, namespace, dest, cache_dir=CACHE_DIR):
    """
    Uses a cached version of a repository, either from a local or remote cache.
    :param alias: The name of the repository
    :param namespace: The Taskcluster namespace to search for remote cache
    :param dest: Destination to clone repository, this destination folder should not exist
    """
    # use the alias like a path, so normalize the path
    local_cache_path = os.path.normpath(
        os.path.join(cache_dir, 'clones', '{}.tar.gz'.format(alias)))

    if not os.path.exists(local_cache_path):
        # download from the remote path
        if not os.path.exists(os.path.dirname(local_cache_path)):
            os.makedirs(os.path.dirname(local_cache_path))

        # retrieve taskid of most recent artifact upload
        task_id = get_latest_taskid(namespace)
        if task_id is None:
            return False

        artifact_path = 'public/{}.tar.gz'.format(alias)

        # create the download url of the artifact
        url = urljoin(TC_QUEUE, 'task', task_id, 'artifacts', artifact_path)
        log.debug("remote cache located '{}'".format(url))
        if not download_file(url, local_cache_path):
            return False

    # untar the file to the destination
    log.debug("extracting {} to {}".format(local_cache_path, dest))
    temp_dir = tempfile.mkdtemp()
    with tarfile.open(local_cache_path, errorlevel=0) as tar:
        tar.extractall(temp_dir)
    tarfolder = os.path.join(temp_dir, os.listdir(temp_dir)[0])
    shutil.move(tarfolder, dest)

    return True


def path_is_hg_repo(repo_path, alias):
    """
    Check if a path is a valid mercurial repository
    :param repo_path: Path to the local mercurial repository
    :param alias: remote that the repository should be pointing to
    :return: bool determining the validity of the path
    """
    hgrc = os.path.join(repo_path, '.hg', 'hgrc')
    if os.path.exists(hgrc):
        with open(hgrc, 'r') as f:
            config = f.read()
            if alias in config:
                log.debug("{} is a valid repository for {}".format(repo_path, alias))
                return True
            else:
                log.debug("{} is an invalid repository for {}".format(repo_path, alias))
                return False
    else:
        log.debug('{} is not a mercurial repository'.format(repo_path))
        return False


def revision(repo):
    try:
        client = hglib.open(repo)
        return client.identify().split()[0]
    except (hglib.error.CommandError, ValueError):
        log.error("unable to get current revision from '{}'".format(repo))
        return None


def clone(url, dest):
    """
    Clone a repository, taking advantage of taskcluster caches
    :param url: URL to the remote repository
    :param dest: Folder to save the repository to
    :return: true is successful, false otherwise
    """
    alias = get_alias(url)
    namespace = '{}.{}'.format(TC_NAMESPACE, hashlib.md5(alias).hexdigest())
    if not os.path.exists(dest):
        # check if we can use a cache
        if not clone_from_cache(alias, namespace, dest):
            # check out a clone
            logging.info("cloning the repository without cache")
            hglib.clone(url, dest)

    if path_is_hg_repo(dest, alias):
        log.debug("pulling latest revisions to repository")
        client = hglib.open(dest)
        return client.pull()
    else:
        log.error("{} exists but is not a known vcs type".format(dest))
        return False


def checkout(directory, base_url, head_url=None, head_rev=None):
    """
    Checkout a repository, taking advantage of taskcluster caches
    :param directory: directory to store the repository
    :param base_url: url to repository to clone from
    :param head_url: url to repository to pull changes from
    :param head_rev: revision to update to
    """
    if clone(base_url, directory):
        client = hglib.open(directory)

        if head_url is None:
            head_url = base_url
        if head_rev is None:
            head_rev = client.branch()

        log.debug("updating {} to revision '{}' from {}".format(directory, head_rev, head_url))
        client.pull(source=head_url, rev=head_rev)
        client.update(rev=head_rev)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', default=None,
                        help='Target directory which to clone and update')
    parser.add_argument('baseUrl', default=None,
                        help='Base repository to clone')
    parser.add_argument('headUrl', default=None, nargs='?',
                        help='Head url to fetch changes from. If this value is not given '
                             'baseUrl is used.')
    parser.add_argument('headRev', default=None, nargs='?',
                        help='Revision/changeset to pull from the repository. If not given '
                             'this defaults to the "tip"/"master" of the default branch.')
    parser.add_argument('headRef', default=None, nargs='?',
                        help=' Reference on head to fetch this should usually be the same '
                             'value as headRev primarily this may be needed for cases where '
                             'you are fetching a revision from a git branch but must fetch the '
                             'reference and then proceed to checkout the particular revision '
                             'you want (git generally does not support pulling specific '
                             'revisions only references). If not given defaults to headRev. '
                             'NOTE: This option is not currently supported and is ignored.')

    logging.basicConfig(level=logging.DEBUG)
    if argv is None:  # pragma: no cover
        argv = sys.argv[1:]

    args = parser.parse_args(argv)
    checkout(args.directory, args.baseUrl, args.headUrl, args.headRev)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
