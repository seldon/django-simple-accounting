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

from django.db.models.signals import post_syncdb

import accounting.models
from accounting.models import AccountType

def create_basic_account_types(sender, app, created_models, verbosity, interactive, **kwargs):
    # execute IFF the DB table for the ``AccountType`` model has just been created
    if AccountType in created_models:  
        # create basic account types
        AccountType.objects.create(name='ROOT', base_type=AccountType.ROOT)
        AccountType.objects.create(name='INCOME', base_type=AccountType.INCOME)
        AccountType.objects.create(name='EXPENSE', base_type=AccountType.EXPENSE)
        AccountType.objects.create(name='ASSET', base_type=AccountType.ASSET)
        AccountType.objects.create(name='LIABILITY', base_type=AccountType.LIABILITY)    

post_syncdb.connect(create_basic_account_types, sender=accounting.models)
