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

from django.db import models

from simple_accounting.lib import queryset_from_iterable 


class AccountManager(models.Manager):
    """
    A custom manager class for the ``Account`` model.
    """
    pass


class TransactionManager(models.Manager):
    """
    A custom manager class for the ``Transaction`` model.
    """
    def get_by_reference(self, refs):
        """
        Take an iterable of model instances (``refs``) and return the queryset
        of ``Transaction``s referring to those instances.        
        Only transactions which refer to *all* passed instances are returned.
        If no transaction satisfying this condition exists, return the empty queryset.
        """
        from django.contrib.contenttypes.models import ContentType
        from simple_accounting.models import TransactionReference
        # FIXME: refine implementation
        qs = self.get_empty_query_set()
        transactions = set(self.get_query_set())
        for ref in refs:
            ct = ContentType.objects.get_for_model(ref)
            obj_id = ref.pk
            trefs = TransactionReference.objects.filter(content_type=ct, object_id=obj_id)
            transactions &= set([tref.transaction for tref in trefs])        
        if transactions:
            queryset_from_iterable(self.model, transactions)
        return qs