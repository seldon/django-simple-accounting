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
from django.contrib.contenttypes.models import ContentType 

from simple_accounting.models import account_type, BasicAccountTypeDict, AccountType
from simple_accounting.models import Subject, AccountSystem, Account, CashFlow, Split, Transaction, LedgerEntry, Invoice
from simple_accounting.exceptions import MalformedPathString, InvalidAccountingOperation, MalformedAccountTree, MalformedTransaction, SubjectiveAPIError
from simple_accounting.utils import register_split_transaction, register_transaction, register_internal_transaction, register_simple_transaction

from simple_accounting.tests.models import Person, GAS, Supplier
from simple_accounting.tests.models import GASSupplierSolidalPact, GASMember
from simple_accounting.tests.models import GASSupplierOrder, GASSupplierOrderProduct, GASMemberOrder, GASSupplierStock
from django.core.exceptions import ValidationError


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
##----------------------------------- TEST CASES ------------------------------#

class SubjectDescriptorTest(TestCase):
    """Tests related to the ``SubjectDescriptor`` descriptor"""
   
    def setUp(self):
        self.person = Person.objects.create(name="Mario", surname="Rossi")
        self.gas = GAS.objects.create(name="GASteropode")
        self.supplier = Supplier.objects.create(name="GoodCompany")
    
    def testGetSucceedOnInstance(self):
        """Check that the ``subject`` attribute can be accessed from model instances"""
        self.person.subject
        self.gas.subject
        self.supplier.subject        

    def testGetFailOnClass(self):
        """Check that the ``subject`` attribute cannot be accessed from the model class"""
        self.assertRaises(AttributeError, lambda: Person.subject)
        self.assertRaises(AttributeError, lambda: GAS.subject)
        self.assertRaises(AttributeError, lambda: Supplier.subject)

    def testSetFailIfInstance(self):  
        """Check that the ``Subject`` attribute is read-only"""
        for instance in self.person, self.gas, self.supplier:
            try:    
                subject = instance.subject
                # just a re-assignment
                instance.subject = subject
            except AttributeError:
                pass
            else:
                raise AssertionError            
            

class EconomicSubjectTest(TestCase):
    """Tests for the ``economic_subject`` decorator"""
    
    def setUp(self):
        self.person = Person.objects.create(name="Mario", surname="Rossi")
        self.gas = GAS.objects.create(name="GASteropode")
        self.supplier = Supplier.objects.create(name="GoodCompany")
    
    def testSubjectCreation(self):
        """When a subjective model is instantiated, a corresponding ``Subject`` instance should be auto-created"""
        for instance in self.person, self.gas, self.supplier:
            content_type = ContentType.objects.get_for_model(instance)
            object_id = instance.pk
            Subject.objects.get(content_type=content_type, object_id=object_id)
            
    def testSubjectAccess(self):
        """Check that ``Subject`` instances can be accessed from the corresponding subjective models instances"""
        for instance in self.person, self.gas, self.supplier:
            content_type = ContentType.objects.get_for_model(instance)
            object_id = instance.pk
            self.assertEqual(instance.subject, Subject.objects.get(content_type=content_type, object_id=object_id))
    
    def testSubjectCleanUp(self):
        """When a subjective model is deleted, the corresponding ``Subject`` instance should be auto-deleted """
        for instance in self.person, self.gas, self.supplier:
            content_type = ContentType.objects.get_for_model(instance)
            object_id = instance.pk
            instance.delete()
            self.assertRaises(Subject.DoesNotExist, Subject.objects.get, content_type=content_type, object_id=object_id)
    
    def testSetupAccountingForSubjectiveModels(self):
        """When a subjective model is instantiated, ``.setup_accounting()`` should be automatically called"""
        for instance in self.person, self.gas, self.supplier:
            subject = instance.subject
            # check that an accounting system for this subject has been created 
            system = AccountSystem.objects.get(owner=subject)
            # check that a root account  has been created
            root = Account.objects.get(system=system, parent=None, name='', kind=account_type.root)
            # check that an `/incomes` account  has been created
            Account.objects.get(system=system, parent=root, name='incomes', kind=account_type.income)
            # check that a `/expenses` account  has been created
            Account.objects.get(system=system, parent=root, name='expenses', kind=account_type.expense)          
            
    def testSetupAccountingForNonSubjectiveModels(self):
        """When a non-subjective model is instantiated, ``.setup_accounting()`` should be automatically called, if defined"""
        ## GAS member
        member = GASMember.objects.create(gas=self.gas, person=self.person)
        ## person-side account-tree changes
        person_system = self.person.accounting.system
        # check that an `/expenses/gas/<gas UID>` account  has been created 
        person_system['/expenses/gas/' + self.gas.uid]
        # check that an `/expenses/gas/<gas UID>/recharges` account  has been created
        person_system['/expenses/gas/' + self.gas.uid + '/recharges']
        # check that an `/expenses/gas/<gas UID>/fees` account  has been created
        person_system['/expenses/gas/' + self.gas.uid + '/fees']
        ## GAS-side account-tree changes
        gas_system = self.gas.accounting.system
        # check that a `/members/<member UID>` account  has been created
        gas_system['/members/' + member.uid]
                
        ## Solidal pact
        pact = GASSupplierSolidalPact.objects.create(gas=self.gas, supplier=self.supplier)
        ## GAS-side account-tree changes
        gas_system = pact.gas.accounting.system
        # check that an `/expenses/suppliers/<supplier UID>` account  has been created 
        gas_system['/expenses/suppliers/' + pact.supplier.uid]
        ## supplier-side account-tree changes
        supplier_system = pact.supplier.accounting.system
        # check that a `/incomes/gas/<GAS UID>` account  has been created
        supplier_system['/incomes/gas/' + pact.gas.uid]       
        
    def testNonSubjectifiableModels(self):
        """A model which already defines a ``subject`` attribute cannot be made 'subjective'"""
        pass
    
        
class SubjectModelTest(TestCase):
    """Tests related to the ``Subject`` model class"""
    
    def setUp(self):
        self.person = Person.objects.create(name="Mario", surname="Rossi")
        # sweep away auto-created ``Subject`` instances        
        Subject.objects.all().delete()
        # sweep away auto-created ``Subject`` instances
        AccountSystem.objects.all().delete()
        self.subject = Subject.objects.create(content_type=ContentType.objects.get_for_model(self.person), object_id=self.person.pk)
        self.system = AccountSystem.objects.create(owner=self.subject)
    
    def testAccountingSystemAccessOK(self):
        """Check that a subject's accounting system (if any) can be accessed from the ``Subject`` instance"""
        self.assertEqual(self.subject.accounting_system, self.system)
    
    def testAccountingSystemAccessFail(self):
        """If an accounting system for a subject hasn't been created yet, raise ``AttributeError``"""
        AccountSystem.objects.all().delete()

        try:
            self.subject.accounting_system
        except AttributeError:
            pass
        else:
            raise AssertionError 
    
    def testAccountingSystemInitialization(self):
        """Check that setup tasks needed for initializing an accounting system are performed when requested"""
        AccountSystem.objects.all().delete()
        Account.objects.all().delete()
        
        self.subject.init_accounting_system()
        
        system = AccountSystem.objects.get(owner=self.subject)
        
        root = Account.objects.get(system=system, parent=None, name='')
        self.assertEqual(root.kind, account_type.root)
        self.assertEqual(root.is_placeholder, True)
        
        incomes = Account.objects.get(system=system, parent=root, name='incomes')
        self.assertEqual(incomes.kind, account_type.income)
        self.assertEqual(incomes.is_placeholder, False)
        
        expenses = Account.objects.get(system=system, parent=root, name='expenses')
        self.assertEqual(expenses.kind, account_type.expense)
        self.assertEqual(expenses.is_placeholder, False)    
    

class AccountTypeModelTest(TestCase):
    """Tests related to the ``AccountType`` model class"""
    
    def setUp(self):
        pass
    
    def testIsStock(self):
        """Check that stock-like account types are correctly recognized"""
        
        for at in (account_type.asset, account_type.liability):
            self.assertEqual(at.is_stock, True)
        
        for at in (account_type.root, account_type.income, account_type.expense):
            self.assertEqual(at.is_stock, False)          
    
    def testIsFlux(self):
        """Check that flux-like account types are correctly recognized"""
    
        for at in (account_type.root, account_type.asset, account_type.liability):
            self.assertEqual(at.is_flux, False)
        
        for at in (account_type.income, account_type.expense):
            self.assertEqual(at.is_flux, True)          
       
     
    def testGetAccounts(self):
        """Check that the property ``.accounts`` works as advertised"""
        person = Person.objects.create(name="Mario", surname="Rossi")
        gas = GAS.objects.create(name="GASteropode")
        supplier = Supplier.objects.create(name="GoodCompany")
        
        # Person account-tree
        person_system = person.accounting.system
        person_root = Account.objects.get(system=person_system, parent=None, name='')
        person_incomes = Account.objects.get(system=person_system, parent=person_root, name='incomes')
        person_expenses = Account.objects.get(system=person_system, parent=person_root, name='expenses')
        person_wallet = Account.objects.get(system=person_system, parent=person_root, name='wallet')
        
        # GAS account-tree
        gas_system = gas.accounting.system
        gas_root = Account.objects.get(system=gas_system, parent=None, name='')
        gas_incomes = Account.objects.get(system=gas_system, parent=gas_root, name='incomes')
        gas_expenses = Account.objects.get(system=gas_system, parent=gas_root, name='expenses')
        gas_cash = Account.objects.get(system=gas_system, parent=gas_root, name='cash')
        gas_members = Account.objects.get(system=gas_system, parent=gas_root, name='members')
        gas_fees = Account.objects.get(system=gas_system, parent=gas_incomes, name='fees')
        gas_recharges = Account.objects.get(system=gas_system, parent=gas_incomes, name='recharges')
        gas_suppliers = Account.objects.get(system=gas_system, parent=gas_expenses, name='suppliers')
        
        # Supplier account-tree
        supplier_system = supplier.accounting.system
        supplier_root = Account.objects.get(system=supplier_system, parent=None, name='')
        supplier_incomes = Account.objects.get(system=supplier_system, parent=supplier_root, name='incomes')
        supplier_expenses = Account.objects.get(system=supplier_system, parent=supplier_root, name='expenses')
        supplier_wallet = Account.objects.get(system=supplier_system, parent=supplier_root, name='wallet')
        supplier_gas = Account.objects.get(system=supplier_system, parent=supplier_incomes, name='gas')      
        
        self.assertEqual(set(account_type.root.accounts), set((person_root, gas_root, supplier_root)))
        self.assertEqual(set(account_type.income.accounts), set((person_incomes, gas_incomes, gas_fees, gas_recharges, supplier_incomes, supplier_gas)))
        self.assertEqual(set(account_type.expense.accounts), set((person_expenses, gas_expenses, gas_suppliers, supplier_expenses)))
        self.assertEqual(set(account_type.asset.accounts), set((person_wallet, gas_cash, gas_members, supplier_wallet)))
        self.assertEqual(set(account_type.liability.accounts), set())
 
    def testNormalizeAccountTypeName(self):
        """Check that the method ``.normalize_account_type_name()`` works as advertised"""
        # WRITEME
        pass   
 
    def testSaveOverride(self):
        """Check that the ``.save()`` ovveride method works as expected"""
        # WRITEME
        pass   


class BasicAccountTypesAccessTest(TestCase):
    """Check that the access API for basic account types works as expected"""
    
    def setUp(self):
        self.d = BasicAccountTypeDict()
    
    def testBasicAccountTypeDictAccessOK(self):
        """If given the name of a basic account type, ``BasicAccountTypeDict`` returns the corresponding model instance"""
        self.assertEqual(self.d['ROOT'], account_type.root)
        self.assertEqual(self.d['INCOME'], account_type.income)
        self.assertEqual(self.d['EXPENSE'], account_type.expense)
        self.assertEqual(self.d['ASSET'], account_type.asset)
        self.assertEqual(self.d['LIABILITY'], account_type.liability)
    
    def testBasicAccountTypeDictAccessFail(self):
        """If given an invalid name, ``BasicAccountTypeDict`` raises KeyError"""
        try:
            self.d['FOO']
        except KeyError:
            pass
        else:
            raise AssertionError 
    
    def testBasicAccountTypeDotAccessOK(self):
        """Basic account types' instances should be accessible as object attributes"""
        self.assertEqual(AccountType.objects.get(name='ROOT'), account_type.root)
        self.assertEqual(AccountType.objects.get(name='INCOME'), account_type.income)
        self.assertEqual(AccountType.objects.get(name='EXPENSE'), account_type.expense)
        self.assertEqual(AccountType.objects.get(name='ASSET'), account_type.asset)
        self.assertEqual(AccountType.objects.get(name='LIABILITY'), account_type.liability)
     
    def testBasicAccountTypeDotAccessFail(self):
        """When accessing a basic account type as an attribute, a wrong name should raise an ``AttributeError``"""
        try:
            account_type.foo
        except AttributeError:
            pass
        else:
            raise AssertionError 
    

class AccountSystemModelTest(TestCase):
    """Tests related to the ``AccountSystem`` model class"""
   
    def setUp(self):
        self.person = Person.objects.create(name="Mario", surname="Rossi")
        self.subject = self.person.subject
        self.system = self.person.accounting.system
        self.root = Account.objects.get(system=self.system, parent=None, name='')
        self.incomes = Account.objects.get(system=self.system, parent=self.root, name='incomes')
        self.expenses = Account.objects.get(system=self.system, parent=self.root, name='expenses')
    
    def testGetRoot(self):
        """Check that the property ``.root()`` works as advertised """
        self.assertEqual(self.system.root, self.root)
    
    def testGetAccounts(self):
        """Check that the property ``.accounts()`` works as advertised """
        self.assertEqual(set(self.system.accounts), set((self.root, self.incomes, self.expenses)))
    
    def testGetTotalAmount(self):
        """Check that the property ``.total_amount()`` works as advertised """
        # WRITEME
        pass   
 
     
class AccountSystemTreeNavigationTest(TestCase):
    """Tests for the account-tree navigation system"""
   
    def setUp(self):
        self.person = Person.objects.create(name="Mario", surname="Rossi")
        self.subject = self.person.subject
        self.system = self.person.accounting.system
        # sweep away auto-created accounts
        Account.objects.all().delete()
        # setup a test account system
        self.root = Account.objects.create(system=self.system, parent=None, name='', kind=account_type.root, is_placeholder=True)
        self.spam = Account.objects.create(system=self.system, parent=self.root, name='spam', kind=account_type.asset)
        self.cheese = Account.objects.create(system=self.system, parent=self.root, name='cheese', kind=account_type.income)
        self.bar = Account.objects.create(system=self.system, parent=self.spam, name='bar', kind=account_type.asset)
        self.baz = Account.objects.create(system=self.system, parent=self.spam, name='baz', kind=account_type.liability)
    
    def testGetAccountFromPathOK(self):
        """Test normal behaviour of the ``.get_account_from_path()`` method"""
        self.assertEqual(self.system.get_account_from_path('/spam'), self.spam)  
        self.assertEqual(self.system.get_account_from_path('/cheese'), self.cheese)
        self.assertEqual(self.system.get_account_from_path('/spam/bar'), self.bar)
        self.assertEqual(self.system.get_account_from_path('/spam/baz'), self.baz)
    
    def testGetAccountFromPathEmptyPath(self):
        """If given the empty path, ``.get_account_from_path()`` should return the root account"""
        self.assertEqual(self.system.get_account_from_path('/'), self.root)
    
    def testGetAccountFromPathFailIfMalformedPathString(self):
        """If ``.get_account_from_path()`` is given a malformed path string, it should raise ``MalformedPathString``"""
        # the empy string is not a valid path 
        self.assertRaises(MalformedPathString, self.system.get_account_from_path, '')
        # a path must start with a single ``ACCOUNT_PATH_SEPARATOR`` occurrence   
        self.assertRaises(MalformedPathString, self.system.get_account_from_path, 'spam')
        self.assertRaises(MalformedPathString, self.system.get_account_from_path, ':spam')
        self.assertRaises(MalformedPathString, self.system.get_account_from_path, '//spam')
        # a path cannot end with ``ACCOUNT_PATH_SEPARATOR``
        self.assertRaises(MalformedPathString, self.system.get_account_from_path, '/spam/')
        # path components must be separated by a single ``ACCOUNT_PATH_SEPARATOR`` occurrence
        self.assertRaises(MalformedPathString, self.system.get_account_from_path, '/spam//bar')       
        
    def testGetAccountFromPathFailIfNotExists(self):
        """If no accounts exist at the given location, ``.get_account_from_path()`` should raise ``Account.DoesNotExist``"""
        self.assertRaises(Account.DoesNotExist, self.system.get_account_from_path, '/bar')
        self.assertRaises(Account.DoesNotExist, self.system.get_account_from_path, '/spam/cheese')
    
    def testGetAccountFromPathExtraSpaces(self):
        """``.get_account_from_path()`` should ignore leading and trailing whitespaces"""
        self.assertEqual(self.system.get_account_from_path(' /spam'), self.spam)
        self.assertEqual(self.system.get_account_from_path('/spam '), self.spam)
    
    def testAccessOK(self):
        """If a valid path string is given, return the account living at that location"""
        self.assertEqual(self.system['/spam'], self.spam)  
        self.assertEqual(self.system['/cheese'], self.cheese)
        self.assertEqual(self.system['/spam/bar'], self.bar)
        self.assertEqual(self.system['/spam/baz'], self.baz)
    
    def testNonExistentAccount(self):
        """If given a well-formed path string but no account exists at that location, raise ``Account.DoesNotExist``"""
        try:    
            self.system['/bar']
            self.system['/spam/cheese']                        
        except Account.DoesNotExist:
            pass
        else:
            raise AssertionError      
    
    def testMalformedPathString(self):
        """If given a malformed path string, raise ``MalformedPathString``"""
        try:
            # the empy string is not a valid path
            self.system[''] 
            # a path must start with a single ``ACCOUNT_PATH_SEPARATOR`` occurrence
            self.system['spam']
            self.system[':spam']
            self.system['//spam'] 
            # a path cannot end with ``ACCOUNT_PATH_SEPARATOR``
            self.system['/spam/']
            # path components must be separated by a single ``ACCOUNT_PATH_SEPARATOR`` occurrence        
            self.system['/spam//bar']
        except MalformedPathString:
            pass
        else:
            raise AssertionError      
    
    def testGetChildOK(self):
        """Check that a given child account can be retrieved, if existing"""
        self.assertEqual(self.root.get_child('spam'), self.spam)  
        self.assertEqual(self.root.get_child('cheese'), self.cheese)
        self.assertEqual(self.spam.get_child('bar'), self.bar)
        self.assertEqual(self.spam.get_child('baz'), self.baz)
        
    def testGetChildFailIfNotExists(self):
        """If no child accounts with a given name exist, raise  ``Account.DoesNotExist``"""
        self.assertRaises(Account.DoesNotExist, self.root.get_child, 'ham')
        self.assertRaises(Account.DoesNotExist, self.cheese.get_child, 'bar')
        self.assertRaises(Account.DoesNotExist, self.spam.get_child, 'ham')
    
    def testGetChildren(self):
        """Check that the method ``.get_children()`` works as advertised"""
        self.assertEqual(set(self.root.get_children()), set((self.spam, self.cheese)))
        self.assertEqual(set(self.spam.get_children()), set((self.bar, self.baz)))


class AccountSystemManipulationTest(TestCase):
    """Tests for the account-tree manipulation API"""
   
    def setUp(self):
        self.person = Person.objects.create(name="Mario", surname="Rossi")
        self.subject = self.person.subject
        self.system = self.person.accounting.system
        # sweep away auto-created accounts
        self.root = Account.objects.create(system=self.system, parent=None, name='', kind=account_type.root, is_placeholder=True)
        self.spam = Account.objects.create(system=self.system, parent=self.root, name='spam', kind=account_type.asset)
        self.cheese = Account.objects.create(system=self.system, parent=self.root, name='cheese', kind=account_type.income)
        self.bar = Account.objects.create(system=self.system, parent=self.spam, name='bar', kind=account_type.asset)
        self.baz = Account.objects.create(system=self.system, parent=self.spam, name='baz', kind=account_type.liability)
    
    def testAddAccountOK(self):
        """Check that adding an account by ``.add_account()`` succeeds if given arguments are valid"""
        self.system.add_account(parent_path='/', name='ham', kind=account_type.expense)
        new_account = Account.objects.get(system=self.system, parent=self.root, name='ham')
        self.assertEqual(new_account.kind, account_type.expense)
        self.assertEqual(new_account.is_placeholder, False)
        
        self.system.add_account(parent_path='/spam', name='egg', kind=account_type.asset, is_placeholder=True)
        new_account = Account.objects.get(system=self.system, parent=self.spam, name='egg')
        self.assertEqual(new_account.kind, account_type.asset)
        self.assertEqual(new_account.is_placeholder, True)

    def testAddAccounthFailIfMalformedPathString(self):
        """If given a malformed path string to the parent account, raise ``MalformedPathString``"""
        self.assertRaises(MalformedPathString, self.system.add_account, parent_path='', name='ham', kind=account_type.asset)
        self.assertRaises(MalformedPathString, self.system.add_account, parent_path='spam', name='ham', kind=account_type.asset)
        self.assertRaises(MalformedPathString, self.system.add_account, parent_path=':spam', name='ham', kind=account_type.asset)
        self.assertRaises(MalformedPathString, self.system.add_account, parent_path='//spam', name='ham', kind=account_type.asset)
        self.assertRaises(MalformedPathString, self.system.add_account, parent_path='/spam/', name='ham', kind=account_type.asset)
        self.assertRaises(MalformedPathString, self.system.add_account, parent_path='/spam//bar', name='ham', kind=account_type.asset)
   
    def testAddAccountFailIfAlreadyExistingChild(self):
        """If specified parent account has already a child named as the given account instance, raise ``InvalidAccountingOperation``"""
        self.assertRaises(InvalidAccountingOperation, self.system.add_account, parent_path='', name='spam', kind=account_type.asset)
        self.assertRaises(InvalidAccountingOperation, self.system.add_account, parent_path='', name='spam', kind=account_type.expense)
        self.assertRaises(InvalidAccountingOperation, self.system.add_account, parent_path='/spam', name='bar', kind=account_type.asset)
        self.assertRaises(InvalidAccountingOperation, self.system.add_account, parent_path='/spam', name='bar', kind=account_type.liability)
            
    def testAddRootAccountOK(self):
        """Check that adding a root account succeeds if it doesn't already exist"""
        Account.objects.all().delete()
        self.system.add_root_account()
        Account.objects.get(system=self.system, parent=None, name='', kind=account_type.root)
    
    def testAddRootAccountFailIfAlreadyExists(self):
        """Check that adding a root account fails if one already exists"""
        self.assertRaises(InvalidAccountingOperation, self.system.add_root_account)
    
    def testAddChildOK(self):
        """Check that adding an account by ``.add_child()`` succeeds if given arguments are valid"""
        self.spam.add_child('ham', kind=account_type.asset)
        ham = Account.objects.get(system=self.system, parent=self.spam, name='ham', kind=account_type.asset)
        ham.delete()
        
        self.spam.add_child('ham', kind=account_type.liability)
        Account.objects.get(system=self.system, parent=self.spam, name='ham', kind=account_type.liability)
        ham.delete()
        
        # check that child's account type defaults to that of its parent
        self.spam.add_child('ham')
        Account.objects.get(system=self.system, parent=self.spam, name='ham', kind=account_type.asset)
    
    def testAddChildFailIfAlreadyExistingChild(self):
        """If a child with that name already exists, `.add_child()`` should raise InvalidAccountingOperation"""
        self.assertRaises(InvalidAccountingOperation, self.spam.add_child, 'bar', kind=account_type.asset)
        self.assertRaises(InvalidAccountingOperation, self.spam.add_child, 'bar', kind=account_type.liability)
    
    
class AccountModelTest(TestCase):
    """Tests related to the ``Account`` model class"""
   
    def setUp(self):
        self.person = Person.objects.create(name="Mario", surname="Rossi")
        self.subject = self.person.subject
        self.system = self.person.accounting.system
        # sweep away auto-created accounts
        Account.objects.all().delete()
        # setup a test account system
        self.root = Account.objects.create(system=self.system, parent=None, name='', kind=account_type.root, is_placeholder=True)
        self.spam = Account.objects.create(system=self.system, parent=self.root, name='spam', kind=account_type.asset)
        self.cheese = Account.objects.create(system=self.system, parent=self.root, name='cheese', kind=account_type.income)
        self.bar = Account.objects.create(system=self.system, parent=self.spam, name='bar', kind=account_type.asset)
        self.baz = Account.objects.create(system=self.system, parent=self.spam, name='baz', kind=account_type.liability)
    
    def testGetBaseType(self):
        """Check that the property ``.base_type`` works as advertised """
        self.assertEqual(self.root.base_type, AccountType.ROOT)   
        self.assertEqual(self.spam.base_type, AccountType.ASSET)
        self.assertEqual(self.cheese.base_type, AccountType.INCOME)
        self.assertEqual(self.bar.base_type, AccountType.ASSET)
        self.assertEqual(self.baz.base_type, AccountType.LIABILITY)
    
    def testIsStock(self):
        """Check that stock-like accounts are correctly recognized"""
        self.assertEqual(self.root.is_stock, False)   
        self.assertEqual(self.spam.is_stock, True)
        self.assertEqual(self.cheese.is_stock, False)
        self.assertEqual(self.bar.is_stock, True)
        self.assertEqual(self.baz.is_stock, True)
    
    def testIsFlux(self):
        """Check that flux-like accounts are correctly recognized"""
        self.assertEqual(self.root.is_flux, False)   
        self.assertEqual(self.spam.is_flux, False)
        self.assertEqual(self.cheese.is_flux, True)
        self.assertEqual(self.bar.is_flux, False)
        self.assertEqual(self.baz.is_flux, False)
    
    def testGetOwner(self):
        """Check that the property ``.owner`` works as advertised"""
        for account in Account.objects.all():
            self.assertEqual(account.owner, self.subject)
    
    def testGetBalance(self):
        """Check that the property ``.balance`` works as advertised"""
        # WRITEME
        pass   
       
    def testGetPath(self):
        """Check that the property ``.path`` works as advertised"""
        self.assertEqual(self.root.path, '/')   
        self.assertEqual(self.spam.path, '/spam')
        self.assertEqual(self.cheese.path, '/cheese')
        self.assertEqual(self.bar.path, '/spam/bar')
        self.assertEqual(self.baz.path, '/spam/bar')
        
    def testIsRoot(self):
        """Check that root accounts are correctly recognized"""
        self.assertEqual(self.root.is_root, True)   
        self.assertEqual(self.spam.is_root, False)
        self.assertEqual(self.cheese.is_root, False)
        self.assertEqual(self.bar.is_root, False)
        self.assertEqual(self.baz.is_root, False)
    
        
    def testGetRoot(self):
        """Check that the property ``.root`` works as advertised"""
        self.assertEqual(self.root.root, self.root)   
        self.assertEqual(self.spam.root, self.root)
        self.assertEqual(self.cheese.root, self.root)
        self.assertEqual(self.bar.root, self.root)
        self.assertEqual(self.baz.root, self.root)
    
    def testGetLedgerEntries(self):
        """Check that the property ``.ledger_entries`` works as advertised"""
        # WRITEME
        pass   
    
  
class AccountModelValidationTest(TestCase):
    """Check validation logic for the ``Account`` model class"""
   
    def setUp(self):
        self.person = Person.objects.create(name="Mario", surname="Rossi")
        self.subject = self.person.subject
        self.system = self.person.accounting.system
        # sweep away auto-created accounts
        Account.objects.all().delete()
        # setup a test account system
        self.root = Account.objects.create(system=self.system, parent=None, name='', kind=account_type.root, is_placeholder=True)
        self.spam = Account.objects.create(system=self.system, parent=self.root, name='spam', kind=account_type.asset)
        self.cheese = Account.objects.create(system=self.system, parent=self.root, name='cheese', kind=account_type.income)
        self.bar = Account.objects.create(system=self.system, parent=self.spam, name='bar', kind=account_type.asset)
        self.baz = Account.objects.create(system=self.system, parent=self.spam, name='baz', kind=account_type.liability)
    
    def testValidationFailIfAccountsBelongToDifferentSystems(self):
        """An account must belong to the same accounting system of its parent, if any"""
        gas = GAS.objects.create(name="GASteropode")
        self.assertRaises(ValidationError, Account.objects.create, system=gas.accounting.system, parent=self.spam, name='ham', kind=account_type.asset)
    
    def testValidationFailIfMixingAccountTypes(self):
        """Stock-like accounts cannot be mixed with flux-like ones"""
        self.assertRaises(ValidationError, Account.objects.create, system=self.system, parent=self.spam, name='ham', kind=account_type.income)
        self.assertRaises(ValidationError, Account.objects.create, system=self.system, parent=self.spam, name='ham', kind=account_type.expense)
        self.assertRaises(ValidationError, Account.objects.create, system=self.system, parent=self.cheese, name='ham', kind=account_type.asset)
        self.assertRaises(ValidationError, Account.objects.create, system=self.system, parent=self.cheese, name='ham', kind=account_type.liability)

    def testValidationFailIfRootAccountNameIsNotEmpty(self):
        """Root accounts must have the empty string as their name"""
        Account.objects.all().delete()
        self.assertRaises(ValidationError, Account.objects.create, system=self.system, parent=None, name='foo', kind=account_type.root, is_placeholder=True)

    def testValidationFailIfNonRootAccountHasEmptyName(self):
        """If an account has an empty string as its name, it must be the root one"""
        self.assertRaises(ValidationError, Account.objects.create, system=self.system, parent=self.root, name='', kind=account_type.income)
        self.assertRaises(ValidationError, Account.objects.create, system=self.system, parent=self.root, name='', kind=account_type.expense)
        self.assertRaises(ValidationError, Account.objects.create, system=self.system, parent=self.root, name='', kind=account_type.asset)
        self.assertRaises(ValidationError, Account.objects.create, system=self.system, parent=self.root, name='', kind=account_type.liability)
        
    def testValidationFailIfAccountNameContainsPathSep(self):
        """Account names can't contain ``ACCOUNT_PATH_SEPARATOR``"""
        self.assertRaises(ValidationError, Account.objects.create, system=self.system, parent=self.root, name='/ham', kind=account_type.income)
        self.assertRaises(ValidationError, Account.objects.create, system=self.system, parent=self.root, name='ha/m', kind=account_type.asset)
        self.assertRaises(ValidationError, Account.objects.create, system=self.system, parent=self.spam, name='ham/', kind=account_type.liability)

class CashFlowModelTest(TestCase):
    """Tests related to the ``CashFlow`` model class"""
   
    def setUp(self):
        self.person = Person.objects.create(name="Mario", surname="Rossi")
        self.subject = self.person.subject
        self.system = self.person.accounting.system
        # sweep away auto-created accounts
        Account.objects.all().delete()
        # setup a test account system
        self.root = Account.objects.create(system=self.system, parent=None, name='', kind=account_type.root, is_placeholder=True)
        self.spam = Account.objects.create(system=self.system, parent=self.root, name='spam', kind=account_type.asset)
        
    def testIsIncoming(self):
        """Check that incoming flows are correctly recognized"""
        cashflow = CashFlow.objects.create(account=self.spam, amount=-3.1) 
        self.assertEqual(cashflow.is_incoming, True)
        
        cashflow = CashFlow.objects.create(account=self.spam, amount=5) 
        self.assertEqual(cashflow.is_incoming, False)
    
    def testIsOutgoing(self):
        """Check that outgoing flows are correctly recognized"""
        cashflow = CashFlow.objects.create(account=self.spam, amount=-3.1) 
        self.assertEqual(cashflow.is_outgoing, False)
        
        cashflow = CashFlow.objects.create(account=self.spam, amount=5) 
        self.assertEqual(cashflow.is_outgoing, True)
    
    def testGetSystem(self):
        """Check that the property ``.system`` works as advertised"""
        cashflow = CashFlow.objects.create(account=self.spam, amount=-3.1)
        self.assertEqual(cashflow.system, self.system) 
    
    
class CashFlowModelValidationTest(TestCase):
    """Check validation logic for ``CashFlow`` model class"""
   
    def setUp(self):
        self.person = Person.objects.create(name="Mario", surname="Rossi")
        self.subject = self.person.subject
        self.system = self.person.accounting.system
        # sweep away auto-created accounts
        Account.objects.all().delete()
        # setup a test account system
        self.root = Account.objects.create(system=self.system, parent=None, name='', kind=account_type.root, is_placeholder=True)
        self.spam = Account.objects.create(system=self.system, parent=self.root, name='spam', kind=account_type.income)
        self.ham = Account.objects.create(system=self.system, parent=self.root, name='ham', kind=account_type.expense)
        
    
    def testValidationFailIfNotAccountIsStock(self):
        """Only stock-like accounts may represent cash-flows"""
        self.assertRaises(ValidationError, CashFlow.objects.create, account=self.root, amount=5.12)
        self.assertRaises(ValidationError, CashFlow.objects.create, account=self.spam, amount=-3.1)
        self.assertRaises(ValidationError, CashFlow.objects.create, account=self.ham, amount=0)
    
    
class SplitModelTest(TestCase):
    """Tests related to the ``Split`` model class"""
   
    def setUp(self):
        self.person = Person.objects.create(name="Mario", surname="Rossi")
        self.gas = GAS.objects.create(name="GASteropode")
        self.person_system = self.person.accounting.system
        self.gas_system = self.gas.accounting.system
        self.member = GASMember.objects.create(gas=self.gas, person=self.person)
        # internal split
        target=CashFlow.objects.create(account=self.gas_system['/cash'], amount=3.1)
        self.internal_split = Split.objects.create(exit_point=None, entry_point=None, target=target)
        # external split
        exit_point=self.person_system['/expenses/gas/' + self.gas.uid + '/recharges']
        entry_point=self.gas_system['/incomes/recharges']
        target=CashFlow.objects.create(account=self.gas_system['/cash'], amount=-3.1)
        self.external_split = Split.objects.create(exit_point=exit_point, entry_point=entry_point, target=target)
    
    def testIsInternal(self):
        """Check that internal splits are correctly recognized"""
        
        self.assertEqual(self.internal_split.is_internal, True)
        self.assertEqual(self.external_split.is_internal, False)
        
    def testGetTargetSystem(self):
        """Check that the property ``.target_system`` works as advertised"""
        self.assertEqual(self.internal_split.target_system, self.gas_system)
        self.assertEqual(self.external_split.target_system, self.gas_system)
    
    def testGetAmount(self):
        """Check that the property ``.amount`` works as advertised"""
        self.assertEqual(self.internal_split.amount, -3.1)
        self.assertEqual(self.external_split.amount, 3.1)
    
    def testGetAccounts(self):
        """Check that the property ``.accounts`` works as advertised"""
        self.assertEqual(self.internal_split.accounts, [None, None, self.gas_system['/cash']])
        self.assertEqual(self.external_split.accounts, [self.person_system['/expenses/gas/' + self.gas.uid + '/recharges'], self.gas_system['/incomes/recharges'], self.gas_system['/cash']])
        
    
class SplitModelValidationTest(TestCase):
    """Check validation logic for ``Split`` model class"""
   
    def setUp(self):
        self.person = Person.objects.create(name="Mario", surname="Rossi")
        self.gas = GAS.objects.create(name="GASteropode")
        self.person_system = self.person.accounting.system
        self.gas_system = self.gas.accounting.system
        self.member = GASMember.objects.create(gas=self.gas, person=self.person)
        
    def testValidationFailIfEntryExitPointNullStatusDiffers(self):
        """If ``exit point`` is null, so must be ``entry_point``"""
        exit_point = self.person_system['/expenses/gas/' + self.gas.uid + '/recharges']
        entry_point = self.gas_system['/incomes/recharges']
        target = CashFlow.objects.create(account=self.gas_system['/cash'], amount=3.1)
        self.assertRaises(ValidationError, Split.objects.create, exit_point=None, entry_point=entry_point, target=target)
        self.assertRaises(ValidationError, Split.objects.create, exit_point=exit_point, entry_point=None, target=target)
    
    def testValidationFailIfExitPointIsNotFluxLike(self):
        """``exit_point`` must be a flux-like account"""
        exit_point = self.person_system['/wallet']
        entry_point = self.gas_system['/incomes/recharges']
        target = CashFlow.objects.create(account=self.gas_system['/cash'], amount=3.1)
        self.assertRaises(ValidationError, Split.objects.create, exit_point=exit_point, entry_point=entry_point, target=target)
    
    def testValidationFailIfEntryPointIsNotFluxLike(self):
        """``entry_point`` must be a flux-like account"""
        exit_point = self.person_system['/expenses/gas/' + self.gas.uid + '/recharges']
        entry_point = self.gas_system['/cash']
        target = CashFlow.objects.create(account=self.gas_system['/cash'], amount=3.1)
        self.assertRaises(ValidationError, Split.objects.create, exit_point=exit_point, entry_point=entry_point, target=target)
    
    def testValidationFailIfTargetIsNotStockLike(self):
        """``target`` must be a stock-like account"""
        exit_point = self.person_system['/expenses/gas/' + self.gas.uid + '/recharges']
        entry_point = self.gas_system['/incomes/recharges']
        target = CashFlow.objects.create(account=self.gas_system['/incomes/recharges'], amount=3.1)
        self.assertRaises(ValidationError, Split.objects.create, exit_point=exit_point, entry_point=entry_point, target=target)
    
    def testValidationFailIfEntryPointAndTargetInDifferentAccountingSystems(self):
        """`entry_point`` must belongs to the same accounting system as ``target``"""
        exit_point=self.person_system['/expenses/gas/' + self.gas.uid + '/recharges']
        entry_point=self.person_system['/expenses/gas/' + self.gas.uid + '/fees']
        target=CashFlow.objects.create(account=self.gas_system['/cash'], amount=3.1)
        self.assertRaises(ValidationError, Split.objects.create, exit_point=exit_point, entry_point=entry_point, target=target)
    

class TransactionModelTest(TestCase):
    """Tests related to the ``Transaction`` model class"""
   
    def setUp(self):
        self.person = Person.objects.create(name="Mario", surname="Rossi")
        self.person2 = Person.objects.create(name="Giorgio", surname="Bianchi")
        self.gas = GAS.objects.create(name="GASteropode")
        self.person_system = self.person.accounting.system
        self.gas_system = self.gas.accounting.system
        self.member = GASMember.objects.create(gas=self.gas, person=self.person)
        self.member2 = GASMember.objects.create(gas=self.gas, person=self.person2)
        
        ## external split transaction
        transaction = Transaction()
        transaction.description = "Test transaction: split & external"
        transaction.issuer = self.person.subject
        transaction.source = CashFlow.objects.create(account=self.person_system['/wallet'], amount=10.0)
        transaction.save()
        # recharge
        exit_point = self.person_system['/expenses/gas/' + self.gas.uid + '/recharges']
        entry_point = self.gas_system['/incomes/recharges']
        target = CashFlow.objects.create(account=self.gas_system['/members/' + self.member.uid], amount=7.2)
        self.split1 = Split.objects.create(exit_point=exit_point, entry_point=entry_point, target=target)
        transaction.split_set.add(self.split1)
        # fee payment
        exit_point = self.person_system['/expenses/gas/' + self.gas.uid + '/fees']
        entry_point = self.gas_system['/incomes/fees']
        target = CashFlow.objects.create(account=self.gas_system['/cash'], amount=2.8)
        self.split2 = Split.objects.create(exit_point=exit_point, entry_point=entry_point, target=target)
        transaction.split_set.add(self.split2)
        self.split_external_tx = transaction
        
        ## internal split transaction
        transaction = Transaction()
        transaction.description = "Test transaction: split & internal"
        transaction.issuer = self.gas.subject
        transaction.source = CashFlow.objects.create(account=self.gas_system['/cash'], amount=0)
        transaction.save()
        # withdraw from Mario Rossi's member account
        target = CashFlow.objects.create(account=self.gas_system['/members/' + self.member.uid], amount=-1.2)
        self.split3 = Split.objects.create(exit_point=None, entry_point=None, target=target)
        transaction.split_set.add(self.split3)
        # Refund to Giorgio Bianchi's member account
        target = CashFlow.objects.create(account=self.gas_system['/members/' + self.member2.uid], amount=1.2)
        self.split4 = Split.objects.create(exit_point=None, entry_point=None, target=target)
        transaction.split_set.add(self.split4)
        self.split_internal_tx = transaction
        
        ## external, non-split transaction
        transaction = Transaction()
        transaction.description = "Test transaction: non-split & external"
        transaction.issuer = self.person.subject
        transaction.source = CashFlow.objects.create(account=self.person_system['/wallet'], amount=10.0)
        transaction.save()
        # recharge
        exit_point = self.person_system['/expenses/gas/' + self.gas.uid + '/recharges']
        entry_point = self.gas_system['/incomes/recharges']
        target = CashFlow.objects.create(account=self.gas_system['/members/' + self.member.uid], amount=10)
        self.split5 = Split.objects.create(exit_point=exit_point, entry_point=entry_point, target=target)
        transaction.split_set.add(self.split5)
        self.external_tx = transaction
        
        ## internal, non-split (i.e. "simple") transaction 
        transaction = Transaction()
        transaction.description = "Test transaction: simple"
        transaction.issuer = self.gas.subject
        transaction.source = CashFlow.objects.create(account=self.gas_system['/members/' + self.member.uid], amount=10.5)
        transaction.save()
        # withdraw from Mario Rossi's member account
        target = CashFlow.objects.create(account=self.gas_system['/cash'], amount=-10.5)
        self.split6 = Split.objects.create(exit_point=None, entry_point=None, target=target)
        transaction.split_set.add(self.split6)
        self.simple_tx = transaction
        
    def testGetSplits(self):
        """Check that the property ``.splits`` works as advertised"""        
        self.assertEqual(set(self.split_external_tx), set((self.split1, self.split2))) 
        self.assertEqual(set(self.split_internal_tx), set((self.split3, self.split4)))
        self.assertEqual(set(self.external_tx), set(self.split5))
        self.assertEqual(set(self.simple_tx), set(self.split6))
        
    def testIsSplit(self):
        """Check that split transactions are correctly recognized"""
        self.assertTrue(self.split_external_tx.is_split)
        self.assertTrue(self.split_internal_tx.is_split)
        self.assertFalse(self.external_tx.is_split)
        self.assertFalse(self.simple_tx.is_split)
    
    def testIsInternal(self):
        """Check that internal transactions are correctly recognized"""
        self.assertFalse(self.split_external_tx.is_split)
        self.assertTrue(self.split_internal_tx.is_split)
        self.assertFalse(self.external_tx.is_split)
        self.assertTrue(self.simple_tx.is_split)
    
    def testIsSimple(self):
        """Check that simple transactions are correctly recognized"""
        self.assertFalse(self.split_external_tx.is_split)
        self.assertFalse(self.split_internal_tx.is_split)
        self.assertFalse(self.external_tx.is_split)
        self.assertTrue(self.simple_tx.is_split)
    
    def testGetLedgerEntries(self):
        """Check that the property ``.ledger_entries`` works as advertised"""
        # WRITEME
        pass
   
    def testGetReferences(self):
        """Check that the property ``.references`` works as advertised"""
        # WRITEME
        pass
    
    def testSetConfirmedOK(self):
        """Check that a transaction can be confirmed if not already so"""
        transaction = self.split_external_tx
        self.assertFalse(transaction.is_confirmed)
        transaction.confirm
        self.assertTrue(transaction.is_confirmed)
        
    def testSetConfirmedFailifAlreadyConfirmed(self):
        """If a transaction had already been confirmed, raise ``InvalidAccountingOperation``"""
        transaction = self.split_external_tx
        self.assertFalse(transaction.is_confirmed)
        transaction.is_confirmed = True
        transaction.save()
        self.assertRaises(InvalidAccountingOperation, transaction.confirm)
        
    def testAddReference(self):
        """Check that the method ``.add_reference()`` works as advertised"""
        # WRITEME
        pass
    
    def testAddReferences(self):
        """Check that the method ``.add_references()`` works as advertised"""
        # WRITEME
        pass
    

class TransactionModelValidationTest(TestCase):
    """Check validation logic for ``Transaction`` model class"""
   
    def setUp(self):
        self.person = Person.objects.create(name="Mario", surname="Rossi")
        self.person2 = Person.objects.create(name="Giorgio", surname="Bianchi")
        self.gas = GAS.objects.create(name="GASteropode")
        self.person_system = self.person.accounting.system
        self.gas_system = self.gas.accounting.system
        self.member = GASMember.objects.create(gas=self.gas, person=self.person)
        self.member2 = GASMember.objects.create(gas=self.gas, person=self.person2)    
    
    def testValidationFailIfConservationOfMoneyNotSatisfied(self):
        """Check that the *law of conservation of money* is satisfied"""
        ## external split transaction
        transaction = Transaction()
        transaction.description = "Test transaction: split & external"
        transaction.issuer = self.person.subject
        transaction.source = CashFlow.objects.create(account=self.person_system['/wallet'], amount=10.0)
        transaction.save()
        # recharge
        exit_point = self.person_system['/expenses/gas/' + self.gas.uid + '/recharges']
        entry_point = self.gas_system['/incomes/recharges']
        target = CashFlow.objects.create(account=self.gas_system['/members/' + self.member.uid], amount=7.2)
        split = Split.objects.create(exit_point=exit_point, entry_point=entry_point, target=target)
        transaction.split_set.add(split)
        # fee payment
        exit_point = self.person_system['/expenses/gas/' + self.gas.uid + '/fees']
        entry_point = self.gas_system['/incomes/fees']
        target = CashFlow.objects.create(account=self.gas_system['/cash'], amount=2.3)
        split = Split.objects.create(exit_point=exit_point, entry_point=entry_point, target=target)
        transaction.split_set.add(split)
        
        ## internal split transaction
        transaction = Transaction()
        transaction.description = "Test transaction: split & internal"
        transaction.issuer = self.gas.subject
        transaction.source = CashFlow.objects.create(account=self.gas_system['/cash'], amount=0)
        transaction.save()
        # withdraw from Mario Rossi's member account
        target = CashFlow.objects.create(account=self.gas_system['/members/' + self.member.uid], amount=-1.2)
        split = Split.objects.create(exit_point=None, entry_point=None, target=target)
        transaction.split_set.add(split)
        # Refund to Giorgio Bianchi's member account
        target = CashFlow.objects.create(account=self.gas_system['/members/' + self.member2.uid], amount=1.1)
        split = Split.objects.create(exit_point=None, entry_point=None, target=target)
        transaction.split_set.add(split)
        
        ## external, non-split transaction
        transaction = Transaction()
        transaction.description = "Test transaction: non-split & external"
        transaction.issuer = self.person.subject
        transaction.source = CashFlow.objects.create(account=self.person_system['/wallet'], amount=10.0)
        transaction.save()
        # recharge
        exit_point = self.person_system['/expenses/gas/' + self.gas.uid + '/recharges']
        entry_point = self.gas_system['/incomes/recharges']
        target = CashFlow.objects.create(account=self.gas_system['/members/' + self.member.uid], amount=9)
        split = Split.objects.create(exit_point=exit_point, entry_point=entry_point, target=target)
        transaction.split_set.add(split)
        
        ## internal, non-split (i.e. "simple") transaction 
        transaction = Transaction()
        transaction.description = "Test transaction: simple"
        transaction.issuer = self.gas.subject
        transaction.source = CashFlow.objects.create(account=self.gas_system['/members/' + self.member.uid], amount=10.5)
        transaction.save()
        # withdraw from Mario Rossi's member account
        target = CashFlow.objects.create(account=self.gas_system['/cash'], amount=10.5)
        split = Split.objects.create(exit_point=None, entry_point=None, target=target)
        transaction.split_set.add(split)
    
    def testValidationFailIfExitPointsAndSourceInDifferentAccountingSystems(self):
        """Exit-points must belong to the same accounting system as the source account"""
        ## external split transaction
        transaction = Transaction()
        transaction.description = "Test transaction: split & external"
        transaction.issuer = self.person.subject
        transaction.source = CashFlow.objects.create(account=self.person_system['/wallet'], amount=10.0)
        transaction.save()
        # recharge
        exit_point = self.gas_system['/incomes/fees']
        entry_point = self.gas_system['/incomes/recharges']
        target = CashFlow.objects.create(account=self.gas_system['/members/' + self.member.uid], amount=7.2)
        split = Split.objects.create(exit_point=exit_point, entry_point=entry_point, target=target)
        transaction.split_set.add(split)
        # fee payment
        exit_point = self.person_system['/expenses/gas/' + self.gas.uid + '/fees']
        entry_point = self.gas_system['/incomes/fees']
        target = CashFlow.objects.create(account=self.gas_system['/cash'], amount=2.8)
        split = Split.objects.create(exit_point=exit_point, entry_point=entry_point, target=target)
        transaction.split_set.add(split)
        
        ## external, non-split transaction
        transaction = Transaction()
        transaction.description = "Test transaction: non-split & external"
        transaction.issuer = self.person.subject
        transaction.source = CashFlow.objects.create(account=self.person_system['/wallet'], amount=10.0)
        transaction.save()
        # recharge
        exit_point = self.person_system['/incomes/fees']
        entry_point = self.gas_system['/incomes/recharges']
        target = CashFlow.objects.create(account=self.gas_system['/members/' + self.member.uid], amount=10)
        split = Split.objects.create(exit_point=exit_point, entry_point=entry_point, target=target)
        transaction.split_set.add(split)
        
    def testValidationFailIfSourceAndTargetsInDifferentAccountingSystemsAndInternal(self):
        """For internal transactions, source and target accounts must belong to the same accounting system"""
        ## internal split transaction
        transaction = Transaction()
        transaction.description = "Test transaction: split & internal"
        transaction.issuer = self.gas.subject
        transaction.source = CashFlow.objects.create(account=self.gas_system['/cash'], amount=0)
        transaction.save()
        # withdraw from Mario Rossi's member account
        target = CashFlow.objects.create(account=self.gas_system['/members/' + self.member.uid], amount=-1.2)
        split = Split.objects.create(exit_point=None, entry_point=None, target=target)
        transaction.split_set.add(split)
        # [Wrong specs] Refund to Giorgio Bianchi's member account 
        target = CashFlow.objects.create(account=self.person_system['/wallet'], amount=1.2)
        split = Split.objects.create(exit_point=None, entry_point=None, target=target)
        transaction.split_set.add(split)
              
        ## internal, non-split (i.e. "simple") transaction 
        transaction = Transaction()
        transaction.description = "Test transaction: simple"
        transaction.issuer = self.gas.subject
        transaction.source = CashFlow.objects.create(account=self.gas_system['/members/' + self.member.uid], amount=10.5)
        transaction.save()
        # [Wrong specs] withdraw from Mario Rossi's member account
        target = CashFlow.objects.create(account=self.person_system['/wallet'], amount=-10.5)
        split = Split.objects.create(exit_point=None, entry_point=None, target=target)
        transaction.split_set.add(split)
     
    def testValidationFailIfAnyIsPlaceholder(self):
        """No account involved in a transaction can be a placeholder one"""
        ## external split transaction
        transaction = Transaction()
        transaction.description = "Test transaction: split & external"
        transaction.issuer = self.person.subject
        transaction.source = CashFlow.objects.create(account=self.person_system['/wallet'], amount=10.0)
        transaction.save()
        # [Wrong specs] recharge
        exit_point = self.person_system['/expenses/gas']
        entry_point = self.gas_system['/incomes/recharges']
        target = CashFlow.objects.create(account=self.gas_system['/members/' + self.member.uid], amount=7.2)
        split = Split.objects.create(exit_point=exit_point, entry_point=entry_point, target=target)
        transaction.split_set.add(split)
        # fee payment
        exit_point = self.person_system['/expenses/gas/' + self.gas.uid + '/fees']
        entry_point = self.gas_system['/incomes/fees']
        target = CashFlow.objects.create(account=self.gas_system['/cash'], amount=2.8)
        split = Split.objects.create(exit_point=exit_point, entry_point=entry_point, target=target)
        transaction.split_set.add(split)
        
        ## internal split transaction
        transaction = Transaction()
        transaction.description = "Test transaction: split & internal"
        transaction.issuer = self.gas.subject
        transaction.source = CashFlow.objects.create(account=self.gas_system['/cash'], amount=0)
        transaction.save()
        # withdraw from Mario Rossi's member account
        target = CashFlow.objects.create(account=self.gas_system['/members/' + self.member.uid], amount=-1.2)
        split = Split.objects.create(exit_point=None, entry_point=None, target=target)
        transaction.split_set.add(split)
        # [Wrong specs] Refund to Giorgio Bianchi's member account
        target = CashFlow.objects.create(account=self.gas_system['/members'], amount=1.2)
        split = Split.objects.create(exit_point=None, entry_point=None, target=target)
        transaction.split_set.add(split)
        
        ## external, non-split transaction
        transaction = Transaction()
        transaction.description = "Test transaction: non-split & external"
        transaction.issuer = self.person.subject
        transaction.source = CashFlow.objects.create(account=self.person_system['/wallet'], amount=10.0)
        transaction.save()
        # [Wrong specs] recharge
        exit_point = self.person_system['/expenses/gas']
        entry_point = self.gas_system['/incomes/recharges']
        target = CashFlow.objects.create(account=self.gas_system['/members/' + self.member.uid], amount=10)
        split = Split.objects.create(exit_point=exit_point, entry_point=entry_point, target=target)
        transaction.split_set.add(split)
        
        ## internal, non-split (i.e. "simple") transaction 
        transaction = Transaction()
        transaction.description = "Test transaction: simple"
        transaction.issuer = self.gas.subject
        # [Wrong specs]
        transaction.source = CashFlow.objects.create(account=self.gas_system['/members'], amount=10.5)
        transaction.save()
        # withdraw from Mario Rossi's member account
        target = CashFlow.objects.create(account=self.gas_system['/cash'], amount=-10.5)
        split = Split.objects.create(exit_point=None, entry_point=None, target=target)
        transaction.split_set.add(split)
    
    
class TransactionReferenceModelTest(TestCase):
    """Tests related to the ``TransactionReference`` model class"""
   
    def setUp(self):
        pass
    
    def testUniquenessConstraints(self):
        """Check that uniqueness constraints for ``TransactionReference`` are enforced at the DB level"""
        # WRITEME
        pass
    
    
class LedgerEntryModelTest(TestCase):
    """Tests related to the ``LedgerEntry`` model class"""
   
    def setUp(self):
        self.person = Person.objects.create(name="Mario", surname="Rossi")
        self.person2 = Person.objects.create(name="Giorgio", surname="Bianchi")
        self.gas = GAS.objects.create(name="GASteropode")
        self.person_system = self.person.accounting.system
        self.gas_system = self.gas.accounting.system
        self.member = GASMember.objects.create(gas=self.gas, person=self.person)
        self.member2 = GASMember.objects.create(gas=self.gas, person=self.person2)
        
        ## external split transaction
        transaction = Transaction()
        transaction.description = "Test transaction: split & external"
        transaction.issuer = self.person.subject
        transaction.source = CashFlow.objects.create(account=self.person_system['/wallet'], amount=10.0)
        transaction.save()
        # recharge
        exit_point = self.person_system['/expenses/gas/' + self.gas.uid + '/recharges']
        entry_point = self.gas_system['/incomes/recharges']
        target = CashFlow.objects.create(account=self.gas_system['/members/' + self.member.uid], amount=7.2)
        self.split1 = Split.objects.create(exit_point=exit_point, entry_point=entry_point, target=target)
        transaction.split_set.add(self.split1)
        # fee payment
        exit_point = self.person_system['/expenses/gas/' + self.gas.uid + '/fees']
        entry_point = self.gas_system['/incomes/fees']
        target = CashFlow.objects.create(account=self.gas_system['/cash'], amount=2.8)
        self.split2 = Split.objects.create(exit_point=exit_point, entry_point=entry_point, target=target)
        transaction.split_set.add(self.split2)
        self.split_external_tx = transaction
        # create ledger entries for this transaction
        self.entry1 = LedgerEntry.objects.create(account=self.person_system['/wallet'], transaction=self.split_external_tx, amount=-10.0)
        self.entry2 = LedgerEntry.objects.create(account=self.person_system['/expenses/gas/' + self.gas.uid + '/recharges'], transaction=self.split_external_tx, amount=7.2)
        self.entry3 = LedgerEntry.objects.create(account=self.person_system['/expenses/gas/' + self.gas.uid + '/fees'], transaction=self.split_external_tx, amount=2.8)
        self.entry4 = LedgerEntry.objects.create(account=self.gas_system['/incomes/recharges'], transaction=self.split_external_tx, amount=7.2)
        self.entry5 = LedgerEntry.objects.create(account=self.gas_system['/incomes/fees'], transaction=self.split_external_tx, amount=2.8)
        self.entry6 = LedgerEntry.objects.create(account=self.gas_system['/members/' + self.member.uid], transaction=self.split_external_tx, amount=7.2)
        self.entry7 = LedgerEntry.objects.create(account=self.gas_system['cash'], transaction=self.split_external_tx, amount=2.8)
        
        ## internal split transaction
        transaction = Transaction()
        transaction.description = "Test transaction: split & internal"
        transaction.issuer = self.gas.subject
        transaction.source = CashFlow.objects.create(account=self.gas_system['/cash'], amount=0)
        transaction.save()
        # withdraw from Mario Rossi's member account
        target = CashFlow.objects.create(account=self.gas_system['/members/' + self.member.uid], amount=-1.2)
        self.split3 = Split.objects.create(exit_point=None, entry_point=None, target=target)
        transaction.split_set.add(self.split3)
        # Refund to Giorgio Bianchi's member account
        target = CashFlow.objects.create(account=self.gas_system['/members/' + self.member2.uid], amount=1.2)
        self.split4 = Split.objects.create(exit_point=None, entry_point=None, target=target)
        transaction.split_set.add(self.split4)
        self.split_internal_tx = transaction
        # create ledger entries for this transaction
        self.entry8 = LedgerEntry.objects.create(account=self.gas_system['cash'], transaction=self.split_internal_tx, amount=0)
        self.entry9 = LedgerEntry.objects.create(account=self.gas_system['/members/' + self.member.uid], transaction=self.split_internal_tx, amount=-1.2)
        self.entry10 = LedgerEntry.objects.create(account=self.gas_system['/members/' + self.member2.uid], transaction=self.split_internal_tx, amount=1.2)
        
        ## external, non-split transaction
        transaction = Transaction()
        transaction.description = "Test transaction: non-split & external"
        transaction.issuer = self.person.subject
        transaction.source = CashFlow.objects.create(account=self.person_system['/wallet'], amount=10.0)
        transaction.save()
        # recharge
        exit_point = self.person_system['/expenses/gas/' + self.gas.uid + '/recharges']
        entry_point = self.gas_system['/incomes/recharges']
        target = CashFlow.objects.create(account=self.gas_system['/members/' + self.member.uid], amount=10)
        self.split5 = Split.objects.create(exit_point=exit_point, entry_point=entry_point, target=target)
        transaction.split_set.add(self.split5)
        self.external_tx = transaction
        # create ledger entries for this transaction
        self.entry11 = LedgerEntry.objects.create(account=self.person_system['/wallet'], transaction=self.external_tx, amount=-10.0)
        self.entry12 = LedgerEntry.objects.create(account=self.person_system['/expenses/gas/' + self.gas.uid + '/recharges'], transaction=self.external_tx, amount=10.0)
        self.entry13 = LedgerEntry.objects.create(account=self.gas_system['/incomes/recharges'], transaction=self.external_tx, amount=10)
        self.entry14 = LedgerEntry.objects.create(account=self.gas_system['/members/' + self.member.uid], transaction=self.external_tx, amount=10)
        
        ## internal, non-split (i.e. "simple") transaction 
        transaction = Transaction()
        transaction.description = "Test transaction: simple"
        transaction.issuer = self.gas.subject
        transaction.source = CashFlow.objects.create(account=self.gas_system['/members/' + self.member.uid], amount=10.5)
        transaction.save()
        # withdraw from Mario Rossi's member account
        target = CashFlow.objects.create(account=self.gas_system['/cash'], amount=-10.5)
        self.split6 = Split.objects.create(exit_point=None, entry_point=None, target=target)
        transaction.split_set.add(self.split6)
        self.simple_tx = transaction
        
        self.entry15 = LedgerEntry.objects.create(account=self.gas_system['/members/' + self.member.uid], transaction=self.simple_tx, amount=-10.5)
        self.entry16 = LedgerEntry.objects.create(account=self.gas_system['cash'], transaction=self.simple_tx, amount=10.5)
    
    def testGetDate(self):
        """Check that the property ``.date`` works as advertised"""
        self.assertEqual(self.entry1, self.split_external_tx.date) 
        self.assertEqual(self.entry2, self.split_external_tx.date)
        self.assertEqual(self.entry3, self.split_external_tx.date)
        self.assertEqual(self.entry4, self.split_external_tx.date) 
        self.assertEqual(self.entry5, self.split_external_tx.date)
        self.assertEqual(self.entry6, self.split_external_tx.date)
        self.assertEqual(self.entry7, self.split_external_tx.date)
        self.assertEqual(self.entry8, self.split_internal_tx.date)
        self.assertEqual(self.entry9, self.split_internal_tx.date)
        self.assertEqual(self.entry10, self.split_internal_tx.date)                        
        self.assertEqual(self.entry11, self.external_tx.date)
        self.assertEqual(self.entry12, self.external_tx.date)
        self.assertEqual(self.entry13, self.external_tx.date)
        self.assertEqual(self.entry14, self.external_tx.date)
        self.assertEqual(self.entry15, self.simple_tx.date)
        self.assertEqual(self.entry16, self.simple_tx.date)        
    
    def testGetSplit(self):
        """Check that the property ``.split`` works as advertised"""
        
        try:
            self.entry1.split
        except AttributeError:
            pass
        else:
            raise AssertionError
 
        self.assertEqual(self.entry2.split, self.split1)
        self.assertEqual(self.entry3.split, self.split2)
        self.assertEqual(self.entry4.split, self.split1) 
        self.assertEqual(self.entry5.split, self.split2)
        self.assertEqual(self.entry6.split, self.split1)
        self.assertEqual(self.entry7.split, self.split2)
        
        try:
            self.entry8.split
        except AttributeError:
            pass
        else:
            raise AssertionError
        
        self.assertEqual(self.entry9.split, self.split3)
        self.assertEqual(self.entry10.split, self.split4)
                                
        try:
            self.entry11.split
        except AttributeError:
            pass
        else:
            raise AssertionError
        
        self.assertEqual(self.entry12.split, self.split5)
        self.assertEqual(self.entry13.split, self.split5)
        self.assertEqual(self.entry14.split, self.split5)
        
        try:
            self.entry15.split
        except AttributeError:
            pass
        else:
            raise AssertionError
        
        
        self.assertEqual(self.entry16.split, self.split6)        
    
    def testGetDescription(self):
        """Check that the property ``.description`` works as advertised"""
        # WRITEME
        pass
        
    def testGetIssuer(self):
        """Check that the property ``.issuer`` works as advertised"""
        self.assertEqual(self.entry1, self.person.subject) 
        self.assertEqual(self.entry2, self.person.subject)
        self.assertEqual(self.entry3, self.person.subject)
        self.assertEqual(self.entry4, self.person.subject) 
        self.assertEqual(self.entry5, self.person.subject)
        self.assertEqual(self.entry6, self.person.subject)
        self.assertEqual(self.entry7, self.person.subject)
        self.assertEqual(self.entry8, self.gas.subject)
        self.assertEqual(self.entry9, self.gas.subject)
        self.assertEqual(self.entry10, self.gas.subject)                        
        self.assertEqual(self.entry11, self.person.subject)
        self.assertEqual(self.entry12, self.person.subject)
        self.assertEqual(self.entry13, self.person.subject)
        self.assertEqual(self.entry14, self.person.subject)
        self.assertEqual(self.entry15, self.gas.subject)
        self.assertEqual(self.entry16, self.gas.subject)        
    
    
    def testNextEntryIdForLedger(self):
        """Check that generation of ledger IDs works as expected"""
        self.assertEqual(self.entry1.entry_id, 1) 
        self.assertEqual(self.entry2.entry_id, 1)
        self.assertEqual(self.entry3.entry_id, 1)
        self.assertEqual(self.entry4.entry_id, 1) 
        self.assertEqual(self.entry5.entry_id, 1)
        self.assertEqual(self.entry6.entry_id, 1)
        self.assertEqual(self.entry7.entry_id, 2)
        self.assertEqual(self.entry8.entry_id, 2)
        self.assertEqual(self.entry9.entry_id, 1)
        self.assertEqual(self.entry10.entry_id, 2)                        
        self.assertEqual(self.entry11.entry_id, 2)
        self.assertEqual(self.entry12.entry_id, 2)
        self.assertEqual(self.entry13.entry_id, 2)
        self.assertEqual(self.entry14.entry_id, 3)
        self.assertEqual(self.entry15.entry_id, 4)
        self.assertEqual(self.entry16.entry_id, 3)        
    
    
    def testSaveOverride(self):
        """Check that the ``.save()`` ovveride method works as expected"""
        # WRITEME
        pass


class InvoiceModelTest(TestCase):
    """Tests related to the ``Invoice`` model class"""
   
    def setUp(self):
        pass
    
    def testGetTotalAmount(self):
        """Check that the property ``.total_amount`` works as advertised"""
        # WRITEME
        pass
    

class AccountingProxyTest(TestCase):
    """Tests related to the ``AccountingProxy`` class"""
   
    def setUp(self):
        pass
    
    def testGetSubject(self):
        """Check that the subject to which the proxy object is attached can be accessed"""
        # WRITEME
        pass
    
    def testGetAccountingSystem(self):
        """Check that the accounting system the proxy object refers to can be accessed"""
        # WRITEME
        pass
    
    def testSubclassing(self):
        """Check that the accounting proxy works even if subclassed"""
        # WRITEME
        pass
    
    def testGetAccount(self):
        """Check that the property ``.account`` works as advertised"""
        # WRITEME
        pass

    def testPayInvoiceFailIfIssuedToAnotherSubject(self):
        """If ``invoice`` was issued to another subject, raise ``InvalidAccountingOperation``"""
        # WRITEME
        pass
    
    def testPayInvoiceFailIfGivenInvalidInstance(self):
        """If ``invoice`` isn't an ``Invoice`` model instance, raise ``ValueError``"""
        # WRITEME
        pass
    
    def testSetInvoicePayedOK(self):
        """Check that the method ``.set_invoice_paid`` works as advertised, if arguments are fine"""
        # WRITEME
        pass
    
    def testSetInvoicePayedFailIfIssuedByAnotherSubject(self):
        """If ``invoice`` was issued by another subject, raise ``InvalidAccountingOperation``"""
        # WRITEME
        pass
    
    def testSetInvoicePayedFailIfGivenInvalidInstance(self):
        """If ``invoice`` isn't an ``Invoice`` model instance, raise ``ValueError``"""
        # WRITEME
        pass

    
class AccountingDescriptorTest(TestCase):
    """Tests related to the ``AccountingDescriptor`` descriptor"""
   
    def setUp(self):
        pass
    
    def testGetSucceedOnInstance(self):
        """Check that the ``accounting`` attribute can be accessed from model instances"""
        # WRITEME
        pass

    def testGetFailOnClass(self):
        """Check that the ``accounting`` attribute cannot be accessed from the model class"""
        # WRITEME
        pass

    def testSetFailIfInstance(self):  
        """Check that the ``accounting`` attribute is read-only"""
        # WRITEME
        pass


class QuerySetFromIterableTest(TestCase):
    """Check that the ``queryset_from_iterable()`` helper function works as advertised"""
   
    def setUp(self):
        pass
    
    def testReturnValueIsQuerySet(self):
        """``queryset_from_iterable`` should return a ``QuerySet`` instance """
        # WRITEME
        pass
    
    def testOK(self):
        """If arguments are valid, check that result is as expected"""
        # WRITEME
        pass
    
    def testEmptyIterable(self):
        """If the iterable is empty, return an ``EmptyQuerySet``"""
        # WRITEME
        pass
    
    def testFailIfNotIterable(self):
        """If argument is not iterable, raise TypeError"""
        # WRITEME
        pass
    
    def testFailIfNotInstancesOfTheSameModel(self):
        """If ``iterable`` contains an instance of the wrong model, raise TypeError"""
        # WRITEME
        pass


class RegisterSplitTransactionTest(TestCase):
    """Check that the ``register_split_transaction()`` factory function works as advertised"""
   
    def setUp(self):
        self.person = Person.objects.create(name="Mario", surname="Rossi")
        self.gas = GAS.objects.create(name="GASteropode")
        self.person_system = self.person.accounting.system
        self.gas_system = self.gas.accounting.system
        self.member = GASMember.objects.create(gas=self.gas, person=self.person)
        
    def testTransactionCreationOK(self):
        """``register_split_transaction()`` should create a new transaction, based on given input"""
        ## external split transaction        
        issuer = self.person.subject
        description="Test transaction: split & external"
        source = CashFlow.objects.create(account=self.person_system['/wallet'], amount=10.0)
        splits = []
        # GAS member recharge
        exit_point = self.person_system['/expenses/gas/' + self.gas.uid + '/recharges']
        entry_point = self.gas_system['/incomes/recharges']
        target = CashFlow.objects.create(account=self.gas_system['/members/' + self.member.uid], amount=7.2)
        split = Split.objects.create(exit_point=exit_point, entry_point=entry_point, target=target)
        splits.append(split)
        # fee payment
        exit_point = self.person_system['/expenses/gas/' + self.gas.uid + '/fees']
        entry_point = self.gas_system['/incomes/fees']
        target = CashFlow.objects.create(account=self.gas_system['/cash'], amount=2.8)
        split = Split.objects.create(exit_point=exit_point, entry_point=entry_point, target=target)
        splits.append(split)
        rv = register_split_transaction(source=source, splits=splits, description=description , issuer=issuer)
        # check that a transaction was indeed created and saved to the DB, according to provided specs
        transaction = Transaction.objects.get(source=source, issuer=issuer, description=description)
        self.assertEqual(set(transaction.splits), set(splits))
        # check that the factory function returns the newly created transaction
        self.assertEqual(transaction, rv)
        
    def testLedgerEntriesCreationOK(self):
        """``register_split_transaction()`` should create implied ledger entries"""
        ## setup
        issuer = self.person.subject
        description="Test transaction: split & external"
        source = CashFlow.objects.create(account=self.person_system['/wallet'], amount=10.0)
        splits = []
        # GAS member recharge
        exit_point = self.person_system['/expenses/gas/' + self.gas.uid + '/recharges']
        entry_point = self.gas_system['/incomes/recharges']
        target = CashFlow.objects.create(account=self.gas_system['/members/' + self.member.uid], amount=7.2)
        split = Split.objects.create(exit_point=exit_point, entry_point=entry_point, target=target)
        splits.append(split)
        # fee payment
        exit_point = self.person_system['/expenses/gas/' + self.gas.uid + '/fees']
        entry_point = self.gas_system['/incomes/fees']
        target = CashFlow.objects.create(account=self.gas_system['/cash'], amount=2.8)
        split = Split.objects.create(exit_point=exit_point, entry_point=entry_point, target=target)
        splits.append(split)
        transaction = register_split_transaction(source=source, splits=splits, description=description , issuer=issuer)
        ## check which ledger entries where created
        self.assertEqual(len(LedgerEntry.objects.all()), 7)
        
        entry = LedgerEntry.objects.get(account=self.person_system['/wallet'], transaction=transaction)
        self.assertEqual(entry.amount, -10)
        self.assertEqual(entry.entry_id, 1)
        
        entry = LedgerEntry.objects.get(account=self.person_system['/expenses/gas/' + self.gas.uid + '/recharges'], transaction=transaction)
        self.assertEqual(entry.amount, 7.2)
        self.assertEqual(entry.entry_id, 1)
        
        entry = LedgerEntry.objects.get(account=self.person_system['/expenses/gas/' + self.gas.uid + '/fees'], transaction=transaction)
        self.assertEqual(entry.amount, 2.8)
        self.assertEqual(entry.entry_id, 1)
        
        entry = LedgerEntry.objects.get(account=self.gas_system['/incomes/recharges'], transaction=transaction)
        self.assertEqual(entry.amount, 7.2)
        self.assertEqual(entry.entry_id, 1)
        
        entry = LedgerEntry.objects.get(account=self.gas_system['/incomes/fees'], transaction=transaction)
        self.assertEqual(entry.amount, 2.8)
        self.assertEqual(entry.entry_id, 1)
        
        entry = LedgerEntry.objects.get(account=self.gas_system['/cash'], transaction=transaction)
        self.assertEqual(entry.amount, 2.8)
        self.assertEqual(entry.entry_id, 1)
        
        entry = LedgerEntry.objects.get(account=self.gas_system['/members/' + self.member.uid], transaction=transaction)
        self.assertEqual(entry.amount, 7.2)
        self.assertEqual(entry.entry_id, 1)
    
    def testFailIfSourceIsNotStockLike(self):
        """If source account is flux-like, raise ``MalformedTransaction``"""
        # WRITEME
        pass
    
    def testFailIfConservationOfMoneyNotSatisfied(self):
        """If provided splits don't satisfy the *law of conservation of money*, raise ``MalformedTransaction``"""
        # WRITEME
        pass
    
    def testFailIfExitPointsAndSourceInDifferentAccountingSystems(self):
        """If exit-points and source account belong to different accounting systems, raise ``MalformedTransaction``"""
        # WRITEME
        pass
    
    def testFailIfSourceAndTargetsInDifferentAccountingSystemsAndInternal(self):
        """If transaction is internal and source and target accounts belong to different accounting systems, raise ``MalformedTransaction``"""
        # WRITEME
        pass
     
    def testFailIfAnyIsPlaceholder(self):
        """If an involved account is a placeholder one, raise ``MalformedTransaction``"""
        # WRITEME
        pass   
    
    def testFailIfEntryExitPointNullStatusDiffers(self):
        """If, for a split, exit-point's and entry-point's null statuses are different, raise ``MalformedTransaction``"""
        # WRITEME
        pass
    
    def testFailIfExitPointIsNotFluxLike(self):
        """If any exit-point is a stock-like account, raise ``MalformedTransaction``"""
        # WRITEME
        pass
    
    def testFailIfEntryPointIsNotFluxLike(self):
        """If any entry-point is a stock-like account, raise ``MalformedTransaction``"""
        # WRITEME
        pass
    
    def testFailIfTargetIsNotStockLike(self):
        """If any target account is not stock-like, raise ``MalformedTransaction``"""
        # WRITEME
        pass
        
    def testFailIfEntryPointAndTargetInDifferentAccountingSystems(self):
        """If, for a split, entry-point belongs to a different accounting system than target account, raise ``MalformedTransaction``"""
        # WRITEME
        pass


class RegisterTransactionTest(TestCase):
    """Check that the ``register_transaction()`` factory function works as advertised"""
   
    def setUp(self):
        self.person = Person.objects.create(name="Mario", surname="Rossi")
        self.gas = GAS.objects.create(name="GASteropode")
        self.person_system = self.person.accounting.system
        self.gas_system = self.gas.accounting.system
        self.member = GASMember.objects.create(gas=self.gas, person=self.person)
    
    def testTransactionCreationOK(self):
        """``register_transaction()`` should create a new transaction, based on given input"""
        ## external, non-split transaction
        description="Test transaction: non-split & external"
        issuer=self.person.subject
        source_account = self.person_system['/wallet']
        # recharge
        exit_point = self.person_system['/expenses/gas/' + self.gas.uid + '/recharges']
        entry_point = self.gas_system['/incomes/recharges']
        target_account = self.gas_system['/members/' + self.member.uid]
        rv = register_transaction(source_account=source_account, exit_point=exit_point, entry_point=entry_point, target_account=target_account, amount=10, description=description, issuer=issuer)
        # check that a transaction was indeed created and saved to the DB, according to provided specs
        transaction = Transaction.objects.get(source__account=source_account, source__amount=10,  issuer=issuer, description=description)
        self.assertEqual(len(transaction.splits), 1)
        # check that the factory function returns the newly created transaction
        self.assertEqual(transaction, rv)
        
    def testLedgerEntriesCreationOK(self):
        """``register_transaction()`` should create implied ledger entries"""
        ## setup
        description="Test transaction: non-split & external"
        issuer=self.person.subject
        source_account = self.person_system['/wallet']
        # recharge
        exit_point = self.person_system['/expenses/gas/' + self.gas.uid + '/recharges']
        entry_point = self.gas_system['/incomes/recharges']
        target_account = self.gas_system['/members/' + self.member.uid]
        transaction = register_transaction(source_account=source_account, exit_point=exit_point, entry_point=entry_point, target_account=target_account, amount=10, description=description, issuer=issuer)
        ## check which ledger entries where created
        self.assertEqual(len(LedgerEntry.objects.all()), 4)
        
        entry = LedgerEntry.objects.get(account=self.person_system['/wallet'], transaction=transaction)
        self.assertEqual(entry.amount, -10)
        self.assertEqual(entry.entry_id, 1)
        
        entry = LedgerEntry.objects.get(account=self.person_system['/expenses/gas/' + self.gas.uid + '/recharges'], transaction=transaction)
        self.assertEqual(entry.amount, 10)
        self.assertEqual(entry.entry_id, 1)
        
        entry = LedgerEntry.objects.get(account=self.gas_system['/incomes/recharges'], transaction=transaction)
        self.assertEqual(entry.amount, 10)
        self.assertEqual(entry.entry_id, 1)
        
        entry = LedgerEntry.objects.get(account=self.gas_system['/members/' + self.member.uid], transaction=transaction)
        self.assertEqual(entry.amount, 10)
        self.assertEqual(entry.entry_id, 1)
       
    def testFailIfSourceIsNotStockLike(self):
        """If source account is flux-like, raise ``MalformedTransaction``"""
        # WRITEME
        pass
    
    def testFailIfExitPointAndSourceInDifferentAccountingSystems(self):
        """If exit-point and source account belong to different accounting systems, raise ``MalformedTransaction``"""
        # WRITEME
        pass
    
    def testFailIfAnyIsPlaceholder(self):
        """If an involved account is a placeholder one, raise ``MalformedTransaction``"""
        # WRITEME
        pass   
    
    def testFailIfEntryOrExitPointNull(self):
        """If either entry-point or exit-point is ``None``,  raise ``MalformedTransaction``"""
        # WRITEME
        pass
    
    def testFailIfExitPointIsNotFluxLike(self):
        """If any exit-point is a stock-like account, raise ``MalformedTransaction``"""
        # WRITEME
        pass
    
    def testFailIfEntryPointIsNotFluxLike(self):
        """If any entry-point is a stock-like account, raise ``MalformedTransaction``"""
        # WRITEME
        pass
    
    def testFailIfTargetIsNotStockLike(self):
        """If any target account is not stock-like, raise ``MalformedTransaction``"""
        # WRITEME
        pass
        
    def testFailIfEntryPointAndTargetInDifferentAccountingSystems(self):
        """If entry-point belongs to a different accounting system than target account, raise ``MalformedTransaction``"""
        # WRITEME
        pass
    

class RegisterInternalTransactionTest(TestCase):
    """Check that the ``register_internal_transaction()`` factory function works as advertised"""
   
    def setUp(self):
        self.person = Person.objects.create(name="Mario", surname="Rossi")
        self.person2 = Person.objects.create(name="Giorgio", surname="Bianchi")
        self.gas = GAS.objects.create(name="GASteropode")
        self.person_system = self.person.accounting.system
        self.gas_system = self.gas.accounting.system
        self.member = GASMember.objects.create(gas=self.gas, person=self.person)
        self.member2 = GASMember.objects.create(gas=self.gas, person=self.person2)
    
    def testTransactionCreationOK(self):
        """``register_internal_transaction()`` should create a new transaction, based on given input"""
        ## internal split transaction
        description="Test transaction: split & internal"
        issuer=self.gas.subject
        source = CashFlow.objects.create(account=self.gas_system['/cash'], amount=0)
        targets = []
        # withdraw from Mario Rossi's member account
        target = CashFlow.objects.create(account=self.gas_system['/members/' + self.member.uid], amount=-1.2)
        targets.append(target)
        # Refund to Giorgio Bianchi's member account
        target = CashFlow.objects.create(account=self.gas_system['/members/' + self.member2.uid], amount=1.2)
        targets.append(target)
        rv = register_internal_transaction(source=source, targets=targets, description=description, issuer=issuer)
        # check that a transaction was indeed created and saved to the DB, according to provided specs
        transaction = Transaction.objects.get(source=source, issuer=issuer, description=description)
        self.assertEqual(len(transaction.splits), 2)
        self.assertTrue(transaction.splits[0].target in targets)
        self.assertTrue(transaction.splits[1].target in targets)
        # check that the factory function returns the newly created transaction
        self.assertEqual(transaction, rv)
        
    def testLedgerEntriesCreationOK(self):
        """``register_internal_transaction()`` should create implied ledger entries"""
        ## setup 
        description="Test transaction: split & internal"
        issuer=self.gas.subject
        source = CashFlow.objects.create(account=self.gas_system['/cash'], amount=0)
        targets = []
        # withdraw from Mario Rossi's member account
        target = CashFlow.objects.create(account=self.gas_system['/members/' + self.member.uid], amount=-1.2)
        targets.append(target)
        # Refund to Giorgio Bianchi's member account
        target = CashFlow.objects.create(account=self.gas_system['/members/' + self.member2.uid], amount=1.2)
        targets.append(target)
        transaction = register_internal_transaction(source=source, targets=targets, description=description, issuer=issuer)
        ## check which ledger entries where created
        self.assertEqual(len(LedgerEntry.objects.all()), 3)
        
        entry = LedgerEntry.objects.get(account=self.gas_system['/members/' + self.member.uid], transaction=transaction)
        self.assertEqual(entry.amount, -1.2)
        self.assertEqual(entry.entry_id, 1)
        
        entry = LedgerEntry.objects.get(account=self.gas_system['/members/' + self.member2.uid], transaction=transaction)
        self.assertEqual(entry.amount, 1.2)
        self.assertEqual(entry.entry_id, 1)
        
        entry = LedgerEntry.objects.get(account=self.gas_system['/cash'], transaction=transaction)
        self.assertEqual(entry.amount, 0)
        self.assertEqual(entry.entry_id, 1)
            
    def testFailIfSourceIsNotStockLike(self):
        """If source account is flux-like, raise ``MalformedTransaction``"""
        # WRITEME
        pass
    
    def testFailIfConservationOfMoneyNotSatisfied(self):
        """If *law of conservation of money* is not satisfied, raise ``MalformedTransaction``"""
        # WRITEME
        pass
    
    def testFailIfSourceAndTargetsInDifferentAccountingSystems(self):
        """If source and target accounts belong to different accounting systems, raise ``MalformedTransaction``"""
        # WRITEME
        pass
     
    def testFailIfAnyIsPlaceholder(self):
        """If an involved account is a placeholder one, raise ``MalformedTransaction``"""
        # WRITEME
        pass   
       
    def testFailIfTargetIsNotStockike(self):
        """If any target account is not stock-like, raise ``MalformedTransaction``"""
        # WRITEME
        pass
        
    
class RegisterSimpleTransactionTest(TestCase):
    """Check that the ``register_simple_transaction()`` factory function works as advertised"""
   
    def setUp(self):
        self.person = Person.objects.create(name="Mario", surname="Rossi")
        self.person2 = Person.objects.create(name="Giorgio", surname="Bianchi")
        self.gas = GAS.objects.create(name="GASteropode")
        self.person_system = self.person.accounting.system
        self.gas_system = self.gas.accounting.system
        self.member = GASMember.objects.create(gas=self.gas, person=self.person)
        self.member2 = GASMember.objects.create(gas=self.gas, person=self.person2)
    
    def testTransactionCreationOK(self):
        """``register_simple_transaction()`` should create a new transaction, based on given input"""
        ## internal, non-split (i.e. "simple") transaction
        description="Test transaction: simple" 
        issuer=self.gas.subject
        source_account = self.gas_system['/members/' + self.member.uid]
        # withdraw from Mario Rossi's member account
        target_account = self.gas_system['/cash']
        rv = register_simple_transaction(source_account=source_account, source__amount=10.5, issuer=issuer, description=description)
        # check that a transaction was indeed created and saved to the DB, according to provided specs
        transaction = Transaction.objects.get(source__account=source_account, )
        self.assertEqual(len(transaction.splits), 1)
        self.assertTrue(transaction.splits[0].target == target_account)
        # check that the factory function returns the newly created transaction
        self.assertEqual(transaction, rv)
        
    def testLedgerEntriesCreationOK(self):
        """``register_simple_transaction()`` should create implied ledger entries"""
        ## setup
        description="Test transaction: simple" 
        issuer=self.gas.subject
        source_account = self.gas_system['/members/' + self.member.uid]
        # withdraw from Mario Rossi's member account
        target_account = self.gas_system['/cash']
        transaction = register_simple_transaction(source_account=source_account, target_account=target_account, amount=10.5, issuer=issuer, description=description)
        ## check which ledger entries where created
        self.assertEqual(len(LedgerEntry.objects.all()), 2)
        
        entry = LedgerEntry.objects.get(account=self.gas_system['/members/' + self.member.uid], transaction=transaction)
        self.assertEqual(entry.amount, -10.5)
        self.assertEqual(entry.entry_id, 1)
        
        entry = LedgerEntry.objects.get(account=self.gas_system['/cash'], transaction=transaction)
        self.assertEqual(entry.amount, 10.5)
        self.assertEqual(entry.entry_id, 1)
    
    def testReturnValueIsTransaction(self):
        """``register_simple_transaction()`` should return the newly created transaction"""
        # WRITEME
        pass
    
    def testFailIfSourceIsNotStockLike(self):
        """If source account is flux-like, raise ``MalformedTransaction``"""
        # WRITEME
        pass
    
    def testFailIfSourceAndTargetsInDifferentAccountingSystems(self):
        """If source and target accounts belong to different accounting systems, raise ``MalformedTransaction``"""
        # WRITEME
        pass
     
    def testFailIfAnyIsPlaceholder(self):
        """If an involved account is a placeholder one, raise ``MalformedTransaction``"""
        # WRITEME
        pass   
    
    def testFailIfTargetIsNotStockLike(self):
        """If target account is not stock-like, raise ``MalformedTransaction``"""
        # WRITEME
        pass
        
        
class UpdateTransactionTest(TestCase):
    """Check that the ``update_transaction()`` factory function works as advertised"""
   
    def setUp(self):
        pass
    
    def testTransactionUpdateOK(self):
        """``update_transaction()`` should update the given transaction, based on provided input"""
        # WRITEME
        pass
    
    def testStaleLedgerEntriesDeletionOK(self):
        """``update_transaction()`` should delete stale ledger entries"""
        # WRITEME
        pass
    
    def testUpdatedLedgerEntriesCreationOK(self):
        """``update_transaction()`` should create implied ledger entries"""
        # WRITEME
        pass
    
    def testReturnValueIsTransaction(self):
        """``update_transaction()`` should return the update transaction"""
        # WRITEME
        pass
    
    def testFailIfSourceIsNotStockLike(self):
        """If updated source account is flux-like, raise ``MalformedTransaction``"""
        # WRITEME
        pass
    
    def testFailIfConservationOfMoneyNotSatisfied(self):
        """If updated splits don't satisfy the *law of conservation of money*, raise ``MalformedTransaction``"""
        # WRITEME
        pass
    
    def testFailIfExitPointsAndSourceInDifferentAccountingSystems(self):
        """If updated exit-points and source account belong to different accounting systems, raise ``MalformedTransaction``"""
        # WRITEME
        pass
    
    def testFailIfSourceAndTargetsInDifferentAccountingSystemsAndInternal(self):
        """If updated transaction is internal and source and target accounts belong to different accounting systems, raise ``MalformedTransaction``"""
        # WRITEME
        pass
     
    def testFailIfAnyIsPlaceholder(self):
        """If an account involved by the updated transaction is a placeholder one, raise ``MalformedTransaction``"""
        # WRITEME
        pass   
    
    def testFailIfEntryExitPointNullStatusDiffers(self):
        """If, for an updated split, exit-point's and entry-point's null statuses are different, raise ``MalformedTransaction``"""
        # WRITEME
        pass
    
    def testFailIfExitPointIsNotFluxLike(self):
        """If any updated exit-point is a stock-like account, raise ``MalformedTransaction``"""
        # WRITEME
        pass
    
    def testFailIfEntryPointIsNotFluxLike(self):
        """If any updated entry-point is a stock-like account, raise ``MalformedTransaction``"""
        # WRITEME
        pass
    
    def testFailIfTargetIsNotStockike(self):
        """If any updated target account is not stock-like, raise ``MalformedTransaction``"""
        # WRITEME
        pass
        
    def testFailIfEntryPointAndTargetInDifferentAccountingSystems(self):
        """If, for an updated split, entry-point belongs to a different accounting system than target account, raise ``MalformedTransaction``"""
        # WRITEME
        pass    