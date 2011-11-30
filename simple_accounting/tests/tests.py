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

from django.test import TestCase

from simple_accounting.tests.models import Person, GAS, Supplier
from simple_accounting.tests.models import GASSupplierSolidalPact, GASMember
from simple_accounting.tests.models import GASSupplierOrder, GASSupplierOrderProduct, GASMemberOrder, GASSupplierStock

class DES(object):
    def __init__(self, people, gases, suppliers):
        self.people = people
        self.gases = gases
        self.suppliers = suppliers

def setup_test_des():
    """
    This function setup a minimal DES ecosystem meant to be used as a test environment.
    """
    ## first, add some people to the DES
    person_names = (
                    "Mario Rossi",
                    "Giorgio Verdi",
                    "Tizio Tizi",
                    "Caio Cai"
                    "Luca Neri",
                    "Alda Bianchi",
                    "Sergio Landi",
                    "Marco Grilli",
                    "Stefania Vanni", 
                    )
    
    people = []
    for s in person_names:
        name, surname = s.split()
        person = Person.objects.create(name, surname)
        people.append(person)
        
    ## then, create some GASs, so people are able to join them
    gas_names = (
                "GASteropode",
                "GASsosa",
                "MiGASo", 
                )

    gases = []
    for s in gas_names:
        gas = GAS.objects.create(name)
        gases.append(gas)
        
    ## now, create some suppliers from which GASs could buy good and services
    supplier_names = (
                    "GoodCompany",
                    "BioNatura",
                    "Acme inc.",
                    "OpenSolutions"
                    "EcoSuole",
                    "ViaggiEtici",
                    "CarniSane",
                    )
    
    suppliers = []
    for s in supplier_names:
        supplier = Supplier.objects.create(name)
        suppliers.append(supplier)
    
    ## add these economic subjects to the DES
    des = DES(people, gases, suppliers)
     
    ## add some solidal pacts 
    pacts = {}
    for rel in ('11', '12', '13', '22', '23'): # GAS number + Supplier number   
        pacts[rel] = GASSupplierSolidalPact.objects.create(des.gases[int(rel[0])], des.suppliers[int(rel[1])]) 
    des.pacts = pacts
     
    return des


class EconomicSubjectTest(TestCase):
    """Tests for the ``economic_subject`` decorator"""
    
    def setUp(self):
        pass
    
    def testSubjectCreation(self):
        """When a subjective model is instantiated, a corresponding ``Subject`` instance should be auto-created"""
        pass
    
    def testSubjectAccess(self):
        """Check that ``Subject`` instances can be accessed from the corresponding subjective models instances"""
        pass
    
    
    def testSubjectCleanUp(self):
        """When a subjective model is deleted, the corresponding ``Subject`` instance should be auto-deleted """
        pass
    
    def testSetupAccounting(self):
        """When a a subjective model is instantiated, the ``.setup_accounting()`` should be automatically called"""
        pass
    
    def testNonSubjectifiableModels(self):
        """A model which already defines a ``subject`` attribute cannot be made 'subjective'"""
        pass
    
        
class SubjectModelTest(TestCase):
    """Tests related to the ``Subject`` model class"""
    
    def setUp(self):
        pass
    
    def testAccountingSystemAccessOK(self):
        """Check that a subject's accounting system (if any) can be accessed from the ``Subject`` instance"""
        pass
    
    def testAccountingSystemAccessFail(self):
        """If an accounting system for a subject hasn't been created yet, raise AttributeError"""
        pass
    
    def testAccountingSystemInitialization(self):
        """Check that setup tasks needed for initializing an accounting system are performed when requested"""
        pass
    

class AccountTypeModelTest(TestCase):
    """Tests related to the ``AccountType`` model class"""
    
    def setUp(self):
        pass
    
    def testIsStock(self):
        """Check that stock-like accounts are correctly recognized"""
        pass   
    
    def testIsFlux(self):
        """Check that flux-like accounts are correctly recognized"""
        pass   
 
     
    def testGetAccounts(self):
        """Check that the property ``.accounts`` works as advertised"""
        pass   
 
    def testNormalizeAccountTypeName(self):
        """Check that the method ``.normalize_account_type_name()`` works as advertised"""
        pass   
 
    def testSaveOverride(self):
        """Check that the ``.save()`` ovveride method works as expected"""
        pass   


class BasicAccountTypesAccessTest(TestCase):
    """Check that the access API for basic account types works as expected"""
    
    def setUp(self):
        pass
    
    def testBasicAccountTypeDictAccessOK(self):
        """If given the name of a basic account type, ``BasicAccountTypeDict`` returns the corresponding model instance"""
        pass
    
    def testBasicAccountTypeDictAccessFail(self):
        """If given an invalid name, ``BasicAccountTypeDict`` raises KeyError"""
        pass    
    
    def testBasicAccountTypeDotAccessOK(self):
        """Basic account types' instances should be accessible as object attributes"""
        pass    
     
    def testBasicAccountTypeDotAccessFail(self):
        """When accessing a basic account type as an attribute, a wrong name should raise an AttributeError"""
        pass    


class AccountSystemModelTest(TestCase):
    """Tests related to the ``AccountSystem`` model class"""
   
    def setUp(self):
        pass
    
    def testGetRoot(self):
        """Check that the property ``.root()`` works as advertised """
        pass   
    
    def testGetAccounts(self):
        """Check that the property ``.accounts()`` works as advertised """
        pass   
    
    def testGetTotalAmount(self):
        """Check that the property ``.total_amount()`` works as advertised """
        pass   
 
     
class AccountSystemTreeNavigationTest(TestCase):
    """Tests for the account-tree navigation system"""
   
    def setUp(self):
        pass
    
    def testAccessOK(self):
        """If a valid path string is given, return the account living at that location"""
        pass
    
    def testNonExistentAccount(self):
        """If given a well-formed path string but no account exists at that location, raise Account.DoesNotExist"""
        pass
    
    def testMalformedPathString(self):
        """If given a malformed path string, raise ValueError"""
        pass
    
    def testGetChildOK(self):
        """Check that a given child account can be retrieved, if existing"""
        pass
    
    def testGetChildFailIfNotExists(self):
        """If no child accounts with a given name exist, raise  Account.DoesNotExist"""
        pass
    
    def testGetChildren(self):
        """Check that the method ``.get_children()`` works as advertised"""
        pass


class AccountSystemManipulationTest(TestCase):
    """Tests for the account-tree manipulation API"""
   
    def setUp(self):
        pass
    
    def testAddAccountOK(self):
        """Check that adding an account by ``.add_account()`` succeeds if given arguments are valid"""
        pass

    def testAddAccounthFailIfMalformedPathString(self):
        """If given a malformed path string to the parent account, raise ValueError"""
        pass
   
    def testAddAccountFailIfAlreadyExistingChild(self):
        """If specified parent account has already a child named as the given account instance, raise InvalidAccountingOperation"""
        pass
        
    def testAddAccountByPathOK(self):
        """If given a valid path string and an ``Account`` instance, add that account under the given location"""
        pass
    
    def testAddAccountByPathFailIfMalformedPathString(self):
        """If given a malformed path string to the parent account, raise ValueError"""
        pass
    
    def testAddAccountByPathFailIfInvalidAccountInstance(self):
        """If given an invalid account instance, raise ValueError"""
        pass

    def testAddAccountByPathFailIfAlreadyExistingChild(self):
        """If specified parent account has already a child named as the given account instance, raise InvalidAccountingOperation"""
        pass
    
    def testAddRootAccountOK(self):
        """Check that adding a root account succeeds if it doesn't already exist"""
        pass
    
    def testAddRootAccountFailIfAlreadyExists(self):
        """Check that adding a root account fails if one already exists"""
        pass
    
    def testAddChildOK(self):
        """Check that adding an account by ``.add_child()`` succeeds if given arguments are valid"""
        pass
    
    def testAddChildFailInvalidAccountInstance(self):
        """If given an invalid account instance to ``.add_child()``, raise ValueError"""
        pass
    
    def testAddChildFailIfAlreadyExistingChild(self):
        """If a child with that name already exists, `.add_child()`` should raise InvalidAccountingOperation"""
        pass
    
    
class AccountModelTest(TestCase):
    """Tests related to the ``Account`` model class"""
   
    def setUp(self):
        pass
    
    def testGetBaseType(self):
        """Check that the property ``.base_type`` works as advertised """
        pass   
    
    def testIsStock(self):
        """Check that stock-like accounts are correctly recognized"""
        pass
    
    def testIsFlux(self):
        """Check that flux-like accounts are correctly recognized"""
        pass
    
    def testGetOwner(self):
        """Check that the property ``.owner`` works as advertised"""
        pass
    
    def testGetBalance(self):
        """Check that the property ``.balance`` works as advertised"""
        pass   
       
    def testGetPath(self):
        """Check that the property ``.path`` works as advertised"""
        pass   
    
    def testIsRoot(self):
        """Check that root accounts are correctly recognized"""
        pass
        
    def testGetRoot(self):
        """Check that the property ``.root`` works as advertised"""
        pass   
    
    def testGetLedgerEntries(self):
        """Check that the property ``.ledger_entries`` works as advertised"""
        pass   
    
  
class AccountModelValidationTest(TestCase):
    """Check validation logic for ``Account`` model class"""
   
    def setUp(self):
        pass
    
    def testValidationFailIfAccountsBelongToDifferentSystems(self):
        """An account must belong to the same accounting system of its parent, if any"""
        pass
    
    def testValidationFailIfMixingAccountTypes(self):
        """Stock-like accounts cannot be mixed with flux-like ones"""
        pass

    def testValidationFailIfRootAccountNameIsNotEmpty(self):
        """Root accounts must have the empty string as their name"""
        pass

    def testValidationFailIfNonRootAccountHasEmptyName(self):
        """If an account has an empty string as its name, it must be the root one"""
        pass

    def testValidationFailIfAccountNameContainsPathSep(self):
        """Account names can't contain ``ACCOUNT_PATH_SEPARATOR``"""
        pass