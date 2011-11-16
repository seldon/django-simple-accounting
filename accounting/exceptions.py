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

# definitions of custom exceptions go here

class AccountingModelException(Exception):
    """
    A base class for accounting-related exceptions.  
    """
    pass

class MalformedAccountTree(AccountingModelException):
    """
    Raised if the tree of accounts associated with an accounting system is malformed.
    (i.e. non-compliant with the reference accounting model).
    """
    pass

class MalformedTransaction(AccountingModelException):
    """
    Raised when encountering a malformed transaction 
    (i.e. non-compliant with the reference accounting model).
    """
    pass

class SubjectiveAPIError(AccountingModelException):
    """
    Raised when a client model can't be declared as *subjective*. 
    """
    pass
        
class InvalidAccountingOperation(AccountingModelException):
    """
    Raised when an invalid accounting operation is requested. 
    """
    pass
