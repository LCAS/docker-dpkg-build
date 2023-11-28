#!/usr/bin/env python3

from ros_buildfarm.config import get_index as get_config_index
from ros_buildfarm.config import get_release_build_files
from ros_buildfarm.config import get_distribution_file
from rosdistro import get_distribution_cache
from rosdistro import get_index
from ros_buildfarm.release_job import _get_direct_dependencies, _get_downstream_package_names
from ros_buildfarm.common import get_debian_package_name
from apt.cache import Cache
from pprint import pprint
from threading import Thread, Lock
from time import sleep

from distro import codename
from github import Github, Auth, WorkflowRun

import sys
from os import environ

class GitHubInterface:

    def __init__(self, token=None, runner_repo="LCAS/docker-dpkg-build", build_workflow_filename='build-package.yaml'):

        if token is None:
            token = environ.get('GH_API_TOKEN', '')
        
        auth = Auth.Token(token)

        self.github = Github(auth=auth)
        self.repo = self.github.get_repo(runner_repo)
        self.build_workflow = self.repo.get_workflow(build_workflow_filename)
        self.workflow_lock = Lock()
    

    def wait_for_completion(self, workflow: WorkflowRun):
        """
        blocks until a GitHub WorkflowRun is concluded. 

        returns the WorkflowRun.conclude string (cancelled, failure, neutral, skipped, stale, success, timed_out)
        
        """
        sleep_time = 1
        _max_sleep = 30
        while True:
            workflow.update()
            # print('  workflow run %s: status: %s, conclusion: %s' % 
            #       (workflow, workflow.status, workflow.conclusion))
            sleep(sleep_time)
            # wait longer and long, up to _max_sleep seconds
            if workflow.conclusion is not None:
                # print('workflow run %s has concluded with %s' %
                #       (workflow, workflow.conclusion))
                break
            else:
                sleep_time += 1 if sleep_time < _max_sleep else _max_sleep

        return workflow.conclusion

    def dispatch_build(self, release_repo, release_tag):
        self.workflow_lock.acquire()
        try:
            previous_runs = set(self.build_workflow.get_runs())
            print('dispatch build job for %s on tag %s', (release_repo, release_tag))
            if not self.build_workflow.create_dispatch(
                'master',
                inputs={
                    'release_repo': release_repo,
                    'release_tag': release_tag
                }
            ):
                raise RuntimeError('couldn\'t dispatch')
            print('wait for run being listed')
            sleep_time = 0.1
            while set(self.build_workflow.get_runs()) == previous_runs:
                sleep(sleep_time)
                sleep_time *= 2 if sleep_time < 5 else 5
            wfs = list(set(self.build_workflow.get_runs()) - previous_runs)
            if len(wfs) != 1:
                raise RuntimeError(
                    'found more than one new run: %s, this mustn\'t happen!',
                     wfs)
            wf = wfs[0]
            # return the workflow object
            return wfs[0]
        finally:
            self.workflow_lock.release()



class AptlyClient:

    def __init__(self, user='lcas', token=None, aptly_url='https://lcas.lincoln.ac.uk/apt/'):
        from aptly_api import Client as AptlyClient
        from requests.auth import HTTPBasicAuth

        if token is None:
            token = environ.get('APTLY_TOKEN', '')

        self.auth = HTTPBasicAuth(user, token)
        self.aptly_url = aptly_url
        self.client = AptlyClient(self.aptly_url, ssl_verify=None, http_auth=self.auth)
    
    def report(self):
        print('\nREPOS:')
        pprint(self.client.repos.list())

        print('\nFILES:')
        pprint(self.client.files.list())

        print('\nPUBLISH:')
        pprint(self.client.publish.list())

        print('\nSNPASHOTS:')
        pprint(self.client.snapshots.list())

class Apt:
    def __init__(self):
        self.deb_cache = Cache()
        self.deb_cache.update()
        self.deb_cache.open()

    def get(self, pkg_name):
        """get the apt.package.Package object, or None if it doesn't exist"""
        try:
            return self.deb_cache[pkg_name]
        except KeyError:
            return None

class DistroBuilder:

    def __init__(self, config_index_url=None, distro = None):
        if config_index_url is None:
            config_index_url = environ.get(
                'ROS_BUILDFARM_CONFIG',
                'https://raw.githubusercontent.com/LCAS/ros_buildfarm_config/ros2/index.yaml'
            )
        self.config_index_url = config_index_url
        if distro is None:
            distro = environ.get('ROS_DISTRO', 'humble')
        self.distro = distro
        self.apt = Apt()

        self.config = get_config_index(self.config_index_url)
        build_files = get_release_build_files(self.config, self.distro)
        build_file = build_files['default']
        print(self.config.rosdistro_index_url)
        index = get_index(self.config.rosdistro_index_url)

        # get targets
        self.platforms = []
        for os_name in build_file.targets.keys():
            for os_code_name in build_file.targets[os_name].keys():
                self.platforms.append((os_name, os_code_name))
        print('The build file contains the following targets:')
        for os_name, os_code_name in self.platforms:
            print('  - %s %s: %s' % (os_name, os_code_name, ', '.join(
                build_file.targets[os_name][os_code_name])))

        self.dist_file = get_distribution_file(index, self.distro, build_file)

        if not self.dist_file:
            print('No distribution file matches the build file')
            return
        self.pkg_names = self.dist_file.release_packages.keys()
        
        self.filtered_pkg_names = build_file.filter_packages(self.pkg_names)
        self.explicitly_ignored_pkg_names = set(self.pkg_names) - set(self.filtered_pkg_names)
        if self.explicitly_ignored_pkg_names:
            print(('The following packages are being %s because of ' +
                'white-/blacklisting:') %
                ('ignored' if build_file.skip_ignored_packages else 'disabled'))
            for pkg_name in sorted(self.explicitly_ignored_pkg_names):
                print('  -', pkg_name)

        self.dist_cache = get_distribution_cache(index, self.distro)

        if self.explicitly_ignored_pkg_names:
            # get direct dependencies from distro cache for each package
            self.direct_dependencies = {}
            for pkg_name in self.pkg_names:
                self.direct_dependencies[pkg_name] = _get_direct_dependencies(
                    pkg_name, self.dist_cache, self.pkg_names) or set([])

            # find recursive downstream deps for all explicitly ignored packages
            self.ignored_pkg_names = set(self.explicitly_ignored_pkg_names)
            while True:
                implicitly_ignored_pkg_names = _get_downstream_package_names(
                    self.ignored_pkg_names, self.direct_dependencies)
                if implicitly_ignored_pkg_names - self.ignored_pkg_names:
                    self.ignored_pkg_names |= implicitly_ignored_pkg_names
                    continue
                break
            implicitly_ignored_pkg_names = \
                self.ignored_pkg_names - self.explicitly_ignored_pkg_names

            if implicitly_ignored_pkg_names:
                print(('The following packages are being %s because their ' +
                    'dependencies are being ignored:') % ('ignored'
                    if build_file.skip_ignored_packages else 'disabled'))
                for pkg_name in sorted(implicitly_ignored_pkg_names):
                    print('  -', pkg_name)
                self.filtered_pkg_names = \
                    set(self.filtered_pkg_names) - implicitly_ignored_pkg_names
        # Remove packages without versions declared.

    def get_package_version(self, pkg_name):
        pkg = self. dist_file.release_packages[pkg_name]
        repo_name = pkg.repository_name
        repo = self.dist_file.repositories[repo_name]
        return repo.release_repository.version

    def get_ordered_packages(self):
        # binary jobs must be generated in topological order
        from catkin_pkg.package import parse_package_string
        from ros_buildfarm.common import topological_order_packages
        pkgs = {}
        for pkg_name in self.pkg_names:
            if pkg_name not in self.dist_cache.release_package_xmls:
                print("Skipping package '%s': no released package.xml in cache" %
                    (pkg_name), file=sys.stderr)
                continue
            pkg_xml = self.dist_cache.release_package_xmls[pkg_name]
            pkg = parse_package_string(pkg_xml)
            pkgs[pkg_name] = pkg
        return topological_order_packages(pkgs)

    def is_uptodate(self, pkg_name, required_version):
        """ check if package is already available in repository
            pkg_name -- ROS key string identifying the package
            required_version -- version strong we need

            return True if the package is already available in the requested version
        """
        # get package from Apt repo
        deb_pkg_name = get_debian_package_name(self.distro, pkg_name)
        pkg = self.apt.get(deb_pkg_name)
        #print(
        #    'check if package "%s" (deb name: "%s") is already available '
        #    'in apt repository with version %s'
        #    % (pkg_name, deb_pkg_name, required_version))

        if pkg is None:
            #print('  no package with name %s in apt cache' % (deb_pkg_name))
            return False

        #print('  found version(s) %s of %s in apt cache; compare against %s' % (
        #    pkg.versions, deb_pkg_name, required_version))
        for pv in pkg.versions:

            if str(pv).split('=')[-1].startswith(required_version):
                return True
        return False
    
    def get_gbp_tag(self, pkg, required_version):
        return 'debian/%s_%s_%s' % (
            get_debian_package_name(self.distro, pkg),
            required_version,
            codename()
        )
    
    def get_release_repository_url(self, pkg_name):
        pkg = self. dist_file.release_packages[pkg_name]
        repo_name = pkg.repository_name
        repo = self.dist_file.repositories[repo_name]
        return repo.release_repository.url


    def run(self):
        pkgs = b.get_ordered_packages()
        github = GitHubInterface()
        print('::group::%s' % 'check all packages in topological order')
        for (k,v) in pkgs:
            #print(v)
            pkg = v['name']
            try:
                required_version = self.get_package_version(pkg)
            except KeyError:
                raise RuntimeError(('::error title=%s::no version found in our distro file. ' % pkg))
            print('check package %s...', pkg)
            if not b.is_uptodate(pkg, required_version):
                tag = self.get_gbp_tag(pkg, required_version)
                url = self.get_release_repository_url(pkg)
                print(' x -> "%s" needs building for version %s\n       (url: %s, tag: %s)' % (
                    pkg, required_version, url, tag))
                job = github.dispatch_build(url, tag)
                print('      dispatched build task for %s, run: %s, waiting for completion...' %
                      (pkg, job.html_url))
                concluded = github.wait_for_completion(job)
                print('      run completed with outcome %s' % concluded)
            else:
                print(' - -> "%s" is up to date already with version %s' % (
                    pkg, required_version))
        print('::endgroup::')

                


#aptly = AptlyClient()
#aptly.report()

#github = GitHubInterface()

#wf = github.dispatch_build(
#    'https://github.com/lcas-releases/topological_navigation.git', 
#    'debian/ros-humble-topological-navigation-msgs_3.0.3-1_jammy')
#github.wait_for_completion(wf)

b = DistroBuilder()
b.run()

# pkgs = b.get_ordered_packages()
# print(b.is_uptodate("desktop"))
# for (k,v) in pkgs:
#     #print(v)
#     pkg = v['name']

#     print(b.is_uptodate(pkg))