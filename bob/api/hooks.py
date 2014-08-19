from __future__ import unicode_literals

from thed import api

from . import forms


@api.Resource.nest('hooks')
class HookResource(api.Resource):

    pass


@api.RestController.register('hooks', context=HookResource)
class HookController(api.RestController):

    @api.decorators.view_config(name='github', request_method='POST')
    def github(self):
        result = forms.GithubForm(self.request.json)
        return api.Response('github.created')

    @api.decorators.view_config(name='travis', request_method='POST')
    def travis(self):
        result = forms.TravisForm(self.request.json)
        if result['build']:
            response = forms.build_threaded(
                result['organization'], result['name'], result['commit']
            )
        else:
            response = 'nope nope nope'

        def iterate_response():
            for lines in response:
                if isinstance(lines, tuple):
                    level, lines = lines
                if not isinstance(lines, list):
                    lines = [lines]
                for line in lines:
                    if not isinstance(line, basestring):
                        line = unicode(line)
                    yield str(line.encode('utf-8'))

        return api.Response(app_iter=iterate_response())