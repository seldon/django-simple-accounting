# Copyright (C) 2011 REES Marche <http://www.reesmarche.org>
#
# This file is part of ``django-simple-accounting``.

# ``django-simple-accounting`` is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# ``django-simple-accounting`` is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with ``django-simple-accounting``. If not, see <http://www.gnu.org/licenses/>.

def queryset_from_iterable(model, iterable):
    """
    Take a model class and an iterable containing instances of that model; 
    return a ``QuerySet`` containing exactly those instances (barring duplicates, if any).
    
    If ``iterable`` contains an object that isn't an instance of ``model``, raise ``TypeError``.
    """
    # collect the set of IDs (i.e. primary keys) of model instances
    # contained in the given iterable (using a ``set`` object as accumulator, 
    # in order to avoid duplicates)
    id_set = set()
    for obj in iterable:
        if obj.__class__ == model:
            id_set.add(obj.pk)
        else:
            raise TypeError(_(u"Can't create a %(model)s QuerySet: %(obj)s is not an instance of model %(model)s"))
    qs = model._default_manager.filter(pk__in=id_set)
    return qs