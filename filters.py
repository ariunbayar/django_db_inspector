from django.db import models
from datetime import datetime


SHORT_FIELDS = [
        models.SmallIntegerField,
        models.PositiveIntegerField,
        models.PositiveIntegerField,
        models.BooleanField,
        models.AutoField,
        models.ForeignKey,
    ]


class RelationField():

    def __init__(self, field):

        self.name = field.name

        self.field = field
        self.model = field.model
        self.is_fk = isinstance(field, models.ForeignKey)
        self.is_rel = isinstance(field, models.ManyToOneRel)

        self.related_model = None
        if self.is_fk:
            related_field = field.remote_field.get_related_field()
            self.related_model = related_field.model

    @property
    def unique_name(self):
        return '%s.%s.%s' % (
                self.model._meta.app_config.name,
                self.model.__name__,
                self.field.name
            )

    @property
    def is_numeric(self):
        return any([isinstance(self.field, t) for t in SHORT_FIELDS])


QS_NO_FILTER = 'qs-no-filter'


class ModelFilter():

    def __init__(self, manager, model):

        self.name = '%s.%s' % (model._meta.app_config.name, model.__name__)

        self.manager = manager
        self.model = model

        fields = [f for f in model._meta.get_fields(include_hidden=True)]
        rfields = [RelationField(f) for f in fields]

        self.rfields = [rf for rf in rfields if not rf.is_fk and not rf.is_rel]
        self.rfields_fk = [rf for rf in rfields if rf.is_fk]
        self.rfields_rel = [rf for rf in rfields if rf.is_rel]

        self.qs = None
        self.qs_fk = None
        self.qs_rel = None
        self.qs_final = None

        self.params = {}
        self.page = None

    def set_filter(self, params):
        self.params = params
        try:
            self.page = int(params.get('_page'))
        except:
            pass

    def get_qs_default(self):
        return self.model.objects.all().order_by('pk')

    def get_qs(self):

        if self.qs is None:
            model = self.model
            params = self.params
            names = [rf.field.name for rf in self.rfields]
            filters = {name: params[name] for name in names if name in params}
            if filters:
                self.qs = self.get_qs_default().filter(**filters)
            else:
                self.qs = QS_NO_FILTER

        return self.qs

    def get_qs_rel(self):

        qs = self.get_qs()

        if self.rfields_rel:
            filters = {}
            for rfield in self.rfields_rel:
                rel_field = rfield.field.remote_field
                remote_qs = self.manager.get_model_filter(rel_field.model).get_qs_rel()
                if remote_qs != QS_NO_FILTER:
                    filters['id__in'] = remote_qs.values_list(rel_field.name)

            if filters:
                if qs == QS_NO_FILTER:
                    qs = self.get_qs_default()
                qs = qs.filter(**filters)

        return qs

    def get_qs_fk(self):

        qs = self.get_qs_rel()

        if self.rfields_fk:
            get_qs_fk = lambda rf: self.manager.get_model_filter(rf.related_model).get_qs_fk()
            pairs = [(rf.field.name, get_qs_fk(rf)) for rf in self.rfields_fk]
            pairs = [(k, remote_qs) for k, remote_qs in pairs if remote_qs != QS_NO_FILTER]
            if pairs:
                if qs == QS_NO_FILTER:
                    qs = self.get_qs_default()
                qs = qs.filter(**{'%s__in' % k: v for k, v in pairs})
            else:
                self.qs = QS_NO_FILTER

        return qs

    def get_row(self, instance, rfield):

        truncate_at = 120

        value = getattr(instance, rfield.name)
        is_truncated = False

        printable_types = [bool, int, str, float, datetime]

        if any([isinstance(value, t) for t in printable_types]):
            rval = value
        else:
            if rfield.is_fk:
                rval = '%s(%s)' % (rfield.model.__name__, value.id)
            else:
                rval = repr(value)

        if isinstance(rval, str) and len(rval) > truncate_at:
            rval = rval[:truncate_at]
            is_truncated = True

        return rval, is_truncated

    def get_qs_final(self):
        if self.qs_final is None:
            qs = self.get_qs_fk()
            if qs == QS_NO_FILTER:
                self.qs_final = self.get_qs_default()
            else:
                self.qs_final = qs
        return self.qs_final

    def get_rows(self):
        qs = self.get_qs_final()
        if self.page:
            n = self.page if self.page <= self.num_pages else 1
            qs = qs[(n - 1) * 20:n * 20]
        else:
            qs = qs[0:20]

        for obj in qs:
            row = [self.get_row(obj, rfield) for rfield in self.fields]
            yield row

    @property
    def count(self):
        return self.get_qs_final().count()

    @property
    def count_total(self):
        return self.model.objects.all().count()

    @property
    def fields(self):

        for rf in self.rfields:
            yield rf

        for rf in self.rfields_fk:
            yield rf

    @property
    def field_filters(self):
        for rfield in self.fields:
            yield rfield, self.params.get(rfield.name)

    @property
    def num_pages(self):
        return int(-(-self.count // 20))


class InspectorFilter():

    def __init__(self, apps, filters):

        app_configs = [app for app in apps.get_app_configs() if not app.name.startswith('django.')]
        models = [m for app in app_configs for m in app.get_models()]

        model_filters = [ModelFilter(self, model) for model in models]
        for model_filter in model_filters:
            model_params = self.extract_model_params(filters, model_filter)
            model_filter.set_filter(dict(model_params))

        self.model_filters = {mf.model: mf for mf in model_filters}

    def extract_model_params(self, filters, model_filter):
        for name, value in filters.items():
            model_name, field_name = name.rsplit('.', 1)
            if model_name == model_filter.name and value:
                yield field_name, value


    def get_model_filter(self, model):
        return self.model_filters[model]

    def __iter__(self):
        for model, model_filter in self.model_filters.items():
            yield model_filter
