from ros_buildfarm.config import get_index as get_config_index
from ros_buildfarm.config import get_release_build_files
from ros_buildfarm.config import get_distribution_file
from rosdistro import get_distribution_cache
from rosdistro import get_index
from ros_buildfarm.release_job import _get_direct_dependencies, _get_downstream_package_names
import sys

class DistroBuilder:

    def __init__(self, config_index_url=None, distro = 'humble'):
        if config_index_url is None:
            self.config_index_url = 'https://raw.githubusercontent.com/LCAS/ros_buildfarm_config/ros2/index.yaml'
        else:
            self.config_index_url = config_index_url
    
        self.distro = distro

        config = get_config_index(self.config_index_url)
        build_files = get_release_build_files(config, self.distro)
        build_file = build_files['default']
        print(config.rosdistro_index_url)
        index = get_index(config.rosdistro_index_url)

        # get targets
        platforms = []
        for os_name in build_file.targets.keys():
            for os_code_name in build_file.targets[os_name].keys():
                platforms.append((os_name, os_code_name))
        print('The build file contains the following targets:')
        for os_name, os_code_name in platforms:
            print('  - %s %s: %s' % (os_name, os_code_name, ', '.join(
                build_file.targets[os_name][os_code_name])))

        dist_file = get_distribution_file(index, self.distro, build_file)

        if not dist_file:
            print('No distribution file matches the build file')
            return
        pkg_names = dist_file.release_packages.keys()
        print(pkg_names)
        filtered_pkg_names = build_file.filter_packages(pkg_names)
        explicitly_ignored_pkg_names = set(pkg_names) - set(filtered_pkg_names)
        if explicitly_ignored_pkg_names:
            print(('The following packages are being %s because of ' +
                'white-/blacklisting:') %
                ('ignored' if build_file.skip_ignored_packages else 'disabled'))
            for pkg_name in sorted(explicitly_ignored_pkg_names):
                print('  -', pkg_name)

        dist_cache = get_distribution_cache(index, distro)

        if explicitly_ignored_pkg_names:
            # get direct dependencies from distro cache for each package
            direct_dependencies = {}
            for pkg_name in pkg_names:
                direct_dependencies[pkg_name] = _get_direct_dependencies(
                    pkg_name, dist_cache, pkg_names) or set([])

            # find recursive downstream deps for all explicitly ignored packages
            ignored_pkg_names = set(explicitly_ignored_pkg_names)
            while True:
                implicitly_ignored_pkg_names = _get_downstream_package_names(
                    ignored_pkg_names, direct_dependencies)
                if implicitly_ignored_pkg_names - ignored_pkg_names:
                    ignored_pkg_names |= implicitly_ignored_pkg_names
                    continue
                break
            implicitly_ignored_pkg_names = \
                ignored_pkg_names - explicitly_ignored_pkg_names

            if implicitly_ignored_pkg_names:
                print(('The following packages are being %s because their ' +
                    'dependencies are being ignored:') % ('ignored'
                    if build_file.skip_ignored_packages else 'disabled'))
                for pkg_name in sorted(implicitly_ignored_pkg_names):
                    print('  -', pkg_name)
                filtered_pkg_names = \
                    set(filtered_pkg_names) - implicitly_ignored_pkg_names


        # binary jobs must be generated in topological order
        from catkin_pkg.package import parse_package_string
        from ros_buildfarm.common import topological_order_packages
        pkgs = {}
        for pkg_name in pkg_names:
            if pkg_name not in dist_cache.release_package_xmls:
                print("Skipping package '%s': no released package.xml in cache" %
                    (pkg_name), file=sys.stderr)
                continue
            pkg_xml = dist_cache.release_package_xmls[pkg_name]
            pkg = parse_package_string(pkg_xml)
            pkgs[pkg_name] = pkg
        ordered_pkg_tuples = topological_order_packages(pkgs)


        #print(dist_cache.)
        print(ordered_pkg_tuples)
b = DistroBuilder()
