from ros_buildfarm.config import get_index as get_config_index
from ros_buildfarm.config import get_release_build_files
from ros_buildfarm.config import get_distribution_file
from rosdistro import get_distribution_cache
from rosdistro import get_index
from ros_buildfarm.release_job import _get_direct_dependencies, _get_downstream_package_names
from apt.cache import Cache
from pprint import pprint

import sys


class Apt:
    def __init__(self):
        self.deb_cache = Cache()

    def get(self, pkg_name):
        """get the apt.package.Package object, or None if it doesn't exist"""
        try:
            return self.deb_cache[pkg_name]
        except KeyError:
            return None

class DistroBuilder:

    def __init__(self, config_index_url=None, distro = 'humble'):
        if config_index_url is None:
            self.config_index_url = 'https://raw.githubusercontent.com/LCAS/ros_buildfarm_config/ros2/index.yaml'
        else:
            self.config_index_url = config_index_url
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

        self.dist_cache = get_distribution_cache(index, distro)

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

    def is_uptodate(self, pkg_name):
        """ check if package is already available in repository
            pkg_name -- ROS key string identifying the package

            return True if the package is already available in the requested version
        """

        # get version from distro 
        try:
            required_version = self.get_package_version(pkg_name)
        except KeyError:
            print('no version for %s found in distro file. Consider up-to-date' % pkg_name)
            required_version=''
            ##return True

        print(
            'check if package %s is already available '
            'in apt repository with version %s'
            % (pkg_name, required_version))

        # get package from Apt repo
        pkg = self.apt.get(pkg_name)

        if pkg is None:
            print('  no package with name %s in cache' % (pkg_name))
            return False

        print('  found version(s) %s of %s in apt cache' % (pkg.versions, pkg_name))
        for pv in pkg.versions:
            if str(pv).startswith(required_version):
                return True
        return False


b = DistroBuilder()
pkgs = b.get_ordered_packages()
print(b.is_uptodate("ros-humble-desktop"))
for (k,v) in pkgs:
    #print(v)
    pkg = v['name']

    print(b.is_uptodate(pkg))