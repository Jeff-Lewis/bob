from __future__ import unicode_literals
import getpass
import logging
import os

from bob.builders import Builder, GithubMixin
from . import forms


logger = logging.getLogger(__name__)


class UbuntuBuilder(Builder, GithubMixin):

    flavor = 'ubuntu'

    dependencies = None

    build_dependencies = None

    before_install = None

    after_install = None

    before_remove = None

    after_remove = None

    exclude = None

    def parse_options(self):
        self._options_parsers['1'] = self._parse_options_v1
        super(UbuntuBuilder, self).parse_options()

    def _parse_options_v1(self):
        settings = self.settings
        result = forms.V1Settings(**settings)
        for key, value in result['targets'][self.flavor].iteritems():
            setattr(self, key, value)
            self.log(key, 'info')
            self.log(value, 'info')
        self.configured = True

    def _install_system_dependencies(self):
        """these are required by the builder and its dependencies e.g. ruby-dev
        for fpm"""
        for command in (
            'sudo apt-get install python-virtualenv ruby-dev gcc ruby1.9.1-dev'
            ' -y',
            'sudo gem install fpm --no-ri --no-rdoc'
        ):
            self.run_command(command)

    def _install_build_dependencies(self):
        """these are required by the project we're building e.g. libpq-dev for
        psycopg"""

        # we don't strictly need self.dependencies but they are good if you
        # want to try installing it locally (debug).
        for deps in (self.build_dependencies, self.dependencies):
            command = 'sudo apt-get install {} -y'.format(
                ' '.join(deps)
            )
            self.run_command(command)

    def _prepare_source(self):
        for exclude in self.exclude:
            self.run_command(
                'find {} -regex "{}" -delete'.format(self.source, exclude)
            )

    @property
    def _venv_env(self):
        env = os.environ.copy()
        env['PATH'] = '{}/embedded/bin:{}'.format(self.target, env['PATH'])

        return env

    def _prepare_target(self):
        for directory in (self.tmp_dir, self.target):
            self.run_command('sudo rm -rf {}'.format(directory))
            self.run_command('sudo mkdir -p {}'.format(directory))
            self.run_command('sudo chown {} {}'.format(
                getpass.getuser(), directory)
            )
        self.run_command('virtualenv -q {}/embedded'.format(self.target))
        self.run_command(
            'pip install setuptools --upgrade',
            env=self._venv_env
        )

    def prepare_system(self):
        super(UbuntuBuilder, self).prepare_system()
        self._install_system_dependencies()
        self._install_build_dependencies()

    def build(self):
        super(UbuntuBuilder, self).build()
        self._prepare_source()
        self._prepare_target()
        build_command = '''
        pip install -b {tmp_dir} \
        --upgrade \
        --install-option=--prefix={embedded_dir} \
        {source_dir}
        '''.format(
            tmp_dir=self.tmp_dir,
            embedded_dir=self.target + '/embedded',
            source_dir=self.source
        )
        self.run_command(
            build_command,
            env=self._venv_env
        )

    def package(self, version, iteration=1):
        super(UbuntuBuilder, self).package(version)
        assert self.configured
        if version[0] == 'v':
            version = version[1:]
        dependencies = ''.join(
            ' -d {}'.format(dep) for dep in self.dependencies
        )
        hooks = ''
        workspace_path = self.source
        for scripts, type in (
            ('before-install', 'before_install'),
            ('after-install', 'after_install'),
            ('before-remove', 'before_remove'),
            ('after-remove', 'after_remove'),
        ):
            hooks += ''.join(
                ' --{}={}/{}'.format(scripts, workspace_path, script)
                for script in (getattr(self, type) or [])
            )
        package_command = '''
        fpm -s dir -t deb -n {project_name} -v {version} -x "*.pyc" \
            --iteration={iteration} \
            {dependencies} \
            {hooks} {dir_to_package}
        '''.format(
            project_name=self.project_name,
            dependencies=dependencies,
            hooks=hooks,
            dir_to_package=self.target,
            version=version,
            iteration=iteration,
        )
        self.run_command(package_command)
        return '{project_name}_{version}-{iteration}_{arch}.deb'.format(
            project_name=self.project_name,
            version=version,
            arch='amd64',
            iteration=1,
        )
