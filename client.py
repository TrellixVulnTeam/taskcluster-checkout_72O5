import hashlib
import urlparse
import urllib2
import argparse
import os
import logging
import json
import tarfile
import hglib
import shutil

tc_namespace = 'tc-vcs.v1.clones'
tc_queue = 'https://queue.taskcluster.net/v1'
tc_index = 'https://index.taskcluster.net/v1'
cache_dir = os.path.join(os.path.expanduser('~'), '.tc-vcs')

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


def lookup_remote_cache(namespace, artifact):
    """
    Lookup a cached version of an artifact from the latest task in a certain namespace.
    :param namespace: namespace of the cache to search
    :param artifact: the name of the artifact to download
    :return: url of the artifact, None if the url is unavailable
    """
    url = urljoin(tc_index, 'task', namespace)
    r = urllib2.urlopen(url)
    try:
        task = json.load(r.read())
    except ValueError:
        logging.warn("Unable to retrieve task from {}".format(url))
        return None

    url = urljoin(tc_queue, 'task', task['taskId'], 'artifacts', artifact)
    return url


def download_file(url, dest, grabchunk=1024 * 4):
    """
    Download a file to disk
    :param url: Url of item to download
    :param dest: path to save the file
    """
    try:
        f = urllib2.urlopen(url)
        log.debug("opened {} for reading".format(url))
        with open(dest, 'wb') as out:
            k = True
            size = 0
            while k:
                indata = f.read(grabchunk)
                out.write(indata)
                size += len(indata)
                if indata == '':
                    k - False
            log.info("File {} downloaded from {}".format(dest, os.path.basename(url)))
    except (urllib2.URLError, urllib2.HTTPError, ValueError) as e:
        log.info("... failed to download {} from {}".format(dest, os.path.basename(url)))
        log.debug("{}".format(e))
    except IOError:
        log.info("failed to write to file for {}".format(dest), exc_info=True)

    return os.path.exists(dest)


def use_cache_if_available(alias, namespace, dest):
    """
    Uses a cached version of a repository, either from a local or remote cache.
    :param alias: The name of the repository
    :param namespace: The Taskcluster namespace to search for remote cache
    :param dest:    :return:
 Destination to clone repository, this destination folder should not exist
    """
    # use the alias like a path, so normalize the path
    local_cache_path = os.path.normpath(os.path.join(cache_dir, 'clones', '{}.tar.gz'.format(alias)))

    if not os.path.exists(local_cache_path):
        # download from the remote path
        if not os.path.exists(os.path.dirname(local_cache_path)):
            os.makedirs(os.path.dirname(local_cache_path))
        artifact_path = 'public/{}.tar.gz'.format(alias)
        url = lookup_remote_cache(namespace, artifact_path)
        if not url:
            logging.info("Failed to find remote cache for {}".format(artifact_path))
            return False
        if not download_file(url, local_cache_path):
            return False

    # untar the file to the destination
    with tarfile.open(local_cache_path) as tar:
        tar.extractall(dest)
    tarfolder = os.path.join(dest, os.listdir(dest)[0])
    for filename in os.listdir(tarfolder):
        shutil.move(os.path.join(tarfolder, filename), os.path.join(dest, filename))
    os.rmdir(tarfolder)

    return True


def valid_hg_repo(repo_path, alias):
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
            return alias in config
    else:
        logging.info('{} is not a mercurial repository'.format(repo_path))
        return False


def clone(url, dest):
    alias = get_alias(url)
    namespace = '{}.{}'.format(tc_namespace, hashlib.md5(alias).hexdigest())
    if os.path.exists(dest):
        logging.info('Path to repository {} at {} already exists'.format(url, dest))
        # check if this is a valid repository
        if not valid_hg_repo(dest, alias):
            return False
    else:
        # check if we can use a cache
        used_cache = use_cache_if_available(alias, namespace, dest)
        if not used_cache:
            # check out a clone
            logging.info("Cloning the repository")
            hglib.clone(url, dest)

    client = hglib.open(dest)
    return client.pull()


def main(argv, _skip_logging=False):
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', default=None,
                        help='Target directory which to clone and update')
    parser.add_argument('baseUrl', default=None,
                        help='Base repository to clone')
    parser.add_argument('headUrl', default=None,
                        help='Head url to fetch changes from. If this value is not given baseUrl '
                             'is used.')
    parser.add_argument('headRev', default=None,
                        help='Revision/changeset to pull from the repository. If not given this '
                             'defaults to the "tip"/"master" of the default branch.')
    parser.add_argument('headRef', default=None,
                        help=' Reference on head to fetch this should usually be the same value as '
                             'headRev primarily this may be needed for cases where you are fetching'
                             ' a revision from a git branch but must fetch the reference and then '
                             'proceed to checkout the particular revision you want (git generally '
                             'does not support pulling specific revisions only references). If not '
                             'given defaults to headRev.')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    clone('https://hg.mozilla.org/build/mozharness', os.path.expanduser('test'))
