### Setup

1. Add following in your `urls.py`:

```
import dbinspector.views

urlpatterns = [
    ...
    path('db/inspector/', dbinspector.views.list, name="dbi-list"),
    ...
]
```

2. Add dbinspector in your `INSTALLED_APPS`:
```
INSTALLED_APPS = [
    ...
    'dbinspector.apps.DbinspectorConfig',
    ...
]
```
