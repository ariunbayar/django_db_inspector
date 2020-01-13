from django.shortcuts import render
from django.apps import apps

from .filters import InspectorFilter


def list(request):

    ifilter = InspectorFilter(apps, request.GET)

    ctx = {
            'ifilter': ifilter,
        }

    return render(request, 'dbinspector/list/index.html', ctx)
