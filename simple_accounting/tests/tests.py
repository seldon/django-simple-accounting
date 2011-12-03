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

from simple_accounting.models import account_type
from simple_accounting.models import Subject, AccountSystem, Account

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
        content_type = ContentType.objects.get_for_model(self.person)
        object_id = self.person.pk
        Subject.objects.get(content_type, object_id)
        
        content_type = ContentType.objects.get_for_model(self.gas)
        object_id = self.gas.pk
        Subject.objects.get(content_type, object_id)
    
        content_type = ContentType.objects.get_for_model(self.supplier)
        object_id = self.supplier.pk
        Subject.objects.get(content_type, object_id)
        
    def testSubjectAccess(self):
        """Check that ``Subject`` instances can be accessed from the corresponding subjective models instances"""
        for instance in self.person, self.gas, self.supplier:
            content_type = ContentType.objects.get_for_model(instance)
            object_id = instance.pk
            self.assertEqual(instance.subject, Subject.objects.get(content_type, object_id))
    
    def testSubjectCleanUp(self):
        """When a subjective model is deleted, the corresponding ``Subject`` instance should be auto-deleted """
        for instance in self.person, self.gas, self.supplier:
            content_type = ContentType.objects.get_for_model(instance)
            object_id = instance.pk
            instance.delete()
            self.assertRaises(Subject.DoesNotExist, Subject.objects.get, content_type, object_id)
    
    def testSetupAccounting(self):
        """When a a subjective model is instantiated, ``.setup_accounting()`` should be automatically called"""
        for subject in self.person, self.gas, self.supplier:
            # check that an accounting system for this subject has been created 
            system = AccountSystem.objects.get(owner=subject)
            # check that a root account  has been created
            root = Account.objects.get(system=system, parent=None, name='', kind=account_type.root)
            # check that an `/incomes` account  has been created
            Account.objects.get(system=system, parent=root, name='incomes', kind=account_type.income)
            # check that a `/expenses` account  has been created
            Account.objects.get(system=system, parent=root, name='expenses', kind=account_type.expense)        
    
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
    
    def testGetAccountFromPathOK(self):
        """Test normal behaviour of the ``.get_account_from_path()`` method"""
        pass
    
    def testGetAccountFromPathEmptyPath(self):
        """If given the empty path, ``.get_account_from_path()`` should return the root account"""
        pass
    
    def testGetAccountFromPathFailIfMalformedPathString(self):
        """If ``.get_account_from_path()`` is given a malformed path string, should raise ValueError"""
        pass
    
    def testGetAccountFromPathFailIfNotExists(self):
        """If no accounts exist at the given location, ``.get_account_from_path()`` should raise Account.DoesNotExist"""
        pass
    
    def testGetAccountFromPathExtraSpaces(self):
        """``.get_account_from_path()`` should ignore leading and trailing whitespaces"""
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


class CashFlowModelTest(TestCase):
    """Tests related to the ``CashFlow`` model class"""
   
    def setUp(self):
        pass
    
    def testIsIncoming(self):
        """Check that incoming flows are correctly recognized"""
        pass
    
    def testIsOutgoing(self):
        """Check that outgoing flows are correctly recognized"""
        pass
    
    def testGetSystem(self):
        """Check that the property ``.system`` works as advertised"""
        pass   
    
    
class CashFlowModelValidationTest(TestCase):
    """Check validation logic for ``CashFlow`` model class"""
   
    def setUp(self):
        pass
    
    def testValidationFailIfNotAccountIsStock(self):
        """Only stock-like accounts may represent cash-flows"""
        pass
    
    
class SplitModelTest(TestCase):
    """Tests related to the ``Split`` model class"""
   
    def setUp(self):
        pass
    
    def testIsInternal(self):
        """Check that internal splits are correctly recognized"""
        pass
    
    def testGetTargetSystem(self):
        """Check that the property ``.target_system`` works as advertised"""
        pass   
    
    def testGetAmount(self):
        """Check that the property ``.amount`` works as advertised"""
        pass
    
    def testGetAccounts(self):
        """Check that the property ``.accounts`` works as advertised"""
        pass
    
    
class SplitModelValidationTest(TestCase):
    """Check validation logic for ``Split`` model class"""
   
    def setUp(self):
        pass
    
    def testValidationFailIfEntryExitPointNullStatusDiffers(self):
        """If ``exit point`` is null, so must be ``entry_point``"""
        pass
    
    def testValidationFailIfExitPointIsNotFluxLike(self):
        """``exit_point`` must be a flux-like account"""
        pass
    
    def testValidationFailIfEntryPointIsNotFluxLike(self):
        """``entry_point`` must be a flux-like account"""
        pass
    
    def testValidationFailIfTargetIsNotStockLike(self):
        """``target`` must be a stock-like account"""
        pass
    
    def testValidationFailIfEntryPointAndTargetInDifferentAccountingSystems(self):
        """`entry_point`` must belongs to the same accounting system as ``target``"""
        pass


class TransactionModelTest(TestCase):
    """Tests related to the ``Transaction`` model class"""
   
    def setUp(self):
        pass
    
    def testGetSplits(self):
        """Check that the property ``.splits`` works as advertised"""
        pass
        
    def testIsSplit(self):
        """Check that split transactions are correctly recognized"""
        pass
    
    def testIsInternal(self):
        """Check that internal transactions are correctly recognized"""
        pass
    
    def testIsSimple(self):
        """Check that simple transactions are correctly recognized"""
        pass
    
    def testGetLedgerEntries(self):
        """Check that the property ``.ledger_entries`` works as advertised"""
        pass
   
    def testGetReferences(self):
        """Check that the property ``.references`` works as advertised"""
        pass
    
    def testSetConfirmedOK(self):
        """Check that a transaction can be confirmed if not already so"""
        pass
    
    def testSetConfirmedFailifAlreadyConfirmed(self):
        """If a transaction had already been confirmed, raise ``InvalidAccountingOperation``"""
        pass
    
    def testAddReference(self):
        """Check that the method ``.add_reference()`` works as advertised"""
        pass
    
    def testAddReferences(self):
        """Check that the method ``.add_references()`` works as advertised"""
        pass
    

class TransactionModelValidationTest(TestCase):
    """Check validation logic for ``Transaction`` model class"""
   
    def setUp(self):
        pass
    
    def testValidationFailIfConservationOfMoneyNotSatisfied(self):
        """Check that the *law of conservation of money* is satisfied"""
        pass
    
    def testValidationFailIfExitPointsAndSourceInDifferentAccountingSystems(self):
        """Exit-points must belong to the same accounting system as the source account"""
        pass
    
    def testValidationFailIfSourceAndTargetsInDifferentAccountingSystemsAndInternal(self):
        """For internal splits, source and target accounts must belong to the same accounting system"""
        pass
     
    def testValidationFailIfAnyIsPlaceholder(self):
        """No account involved in a transaction can be a placeholder one"""
        pass   
    
    
class TransactionReferenceModelTest(TestCase):
    """Tests related to the ``TransactionReference`` model class"""
   
    def setUp(self):
        pass
    
    def testUniquenessConstraints(self):
        """Check that uniqueness constraints for ``TransactionReference`` are enforced at the DB level"""
        pass
    
    
class LedgerEntryModelTest(TestCase):
    """Tests related to the ``LedgerEntry`` model class"""
   
    def setUp(self):
        pass
    
    def testGetDate(self):
        """Check that the property ``.date`` works as advertised"""
        pass
    
    def testGetSplit(self):
        """Check that the property ``.split`` works as advertised"""
        pass
    
    def testGetDescription(self):
        """Check that the property ``.description`` works as advertised"""
        pass
        
    def testGetIssuer(self):
        """Check that the property ``.issuer`` works as advertised"""
        pass
    
    def testNextEntryIdForLedger(self):
        """Check that generation of ledger IDs works as expected"""
        pass
    
    def testSaveOverride(self):
        """Check that the ``.save()`` ovveride method works as expected"""
        pass


class InvoiceModelTest(TestCase):
    """Tests related to the ``Invoice`` model class"""
   
    def setUp(self):
        pass
    
    def testGetTotalAmount(self):
        """Check that the property ``.total_amount`` works as advertised"""
        pass
    

class AccountingProxyTest(TestCase):
    """Tests related to the ``AccountingProxy`` class"""
   
    def setUp(self):
        pass
    
    def testGetSubject(self):
        """Check that the subject to which the proxy object is attached can be accessed"""
        pass
    
    def testGetAccountingSystem(self):
        """Check that the accounting system the proxy object refers to can be accessed"""
        pass
    
    def testSubclassing(self):
        """Check that the accounting proxy works even if subclassed"""
        pass
    
    def testGetAccount(self):
        """Check that the property ``.account`` works as advertised"""
        pass

    def testPayInvoiceFailIfIssuedToAnotherSubject(self):
        """If ``invoice`` was issued to another subject, raise ``InvalidAccountingOperation``"""
        pass
    
    def testPayInvoiceFailIfGivenInvalidInstance(self):
        """If ``invoice`` isn't an ``Invoice`` model instance, raise ``ValueError``"""
        pass
    
    def testSetInvoicePayedOK(self):
        """Check that the method ``.set_invoice_paid`` works as advertised, if arguments are fine"""
        pass
    
    def testSetInvoicePayedFailIfIssuedByAnotherSubject(self):
        """If ``invoice`` was issued by another subject, raise ``InvalidAccountingOperation``"""
        pass
    
    def testSetInvoicePayedFailIfGivenInvalidInstance(self):
        """If ``invoice`` isn't an ``Invoice`` model instance, raise ``ValueError``"""
        pass

    
class AccountingDescriptorTest(TestCase):
    """Tests related to the ``AccountingDescriptor`` descriptor"""
   
    def setUp(self):
        pass
    
    def testGetSucceedOnInstance(self):
        """Check that the ``accounting`` attribute can be accessed from model instances"""
        pass

    def testGetFailOnClass(self):
        """Check that the ``accounting`` attribute cannot be accessed from the model class"""
        pass

    def testSetFailIfInstance(self):  
        """Check that the ``accounting`` attribute is read-only"""
        pass


class QuerySetFromIterableTest(TestCase):
    """Check that the ``queryset_from_iterable()`` helper function works as advertised"""
   
    def setUp(self):
        pass
    
    def testReturnValueIsQuerySet(self):
        """``queryset_from_iterable`` should return a ``QuerySet`` instance """
        pass
    
    def testOK(self):
        """If arguments are valid, check that result is as expected"""
        pass
    
    def testEmptyIterable(self):
        """If the iterable is empty, return an ``EmptyQuerySet``"""
        pass
    
    def testFailIfNotIterable(self):
        """If argument is not iterable, raise TypeError"""
        pass
    
    def testFailIfNotInstancesOfTheSameModel(self):
        """If ``iterable`` contains an instance of the wrong model, raise TypeError"""
        pass


class RegisterSplitTransactionTest(TestCase):
    """Check that the ``register_split_transaction()`` factory function works as advertised"""
   
    def setUp(self):
        pass
    
    def testTransactionCreationOK(self):
        """``register_split_transaction()`` should create a new transaction, based on given input"""
        pass
    
    def testLedgerEntriesCreationOK(self):
        """``register_split_transaction()`` should create implied ledger entries"""
        pass
    
    def testReturnValueIsTransaction(self):
        """``register_split_transaction()`` should return the newly created transaction"""
        pass
    
    def testFailIfSourceIsNotStockLike(self):
        """If source account is flux-like, raise ``MalformedTransaction``"""
        pass
    
    def testFailIfConservationOfMoneyNotSatisfied(self):
        """If provided splits don't satisfy the *law of conservation of money*, raise ``MalformedTransaction``"""
        pass
    
    def testFailIfExitPointsAndSourceInDifferentAccountingSystems(self):
        """If exit-points and source account belong to different accounting systems, raise ``MalformedTransaction``"""
        pass
    
    def testFailIfSourceAndTargetsInDifferentAccountingSystemsAndInternal(self):
        """If transaction is internal and source and target accounts belong to different accounting systems, raise ``MalformedTransaction``"""
        pass
     
    def testFailIfAnyIsPlaceholder(self):
        """If an involved account is a placeholder one, raise ``MalformedTransaction``"""
        pass   
    
    def testFailIfEntryExitPointNullStatusDiffers(self):
        """If, for a split, exit-point's and entry-point's null statuses are different, raise ``MalformedTransaction``"""
        pass
    
    def testFailIfExitPointIsNotFluxLike(self):
        """If any exit-point is a stock-like account, raise ``MalformedTransaction``"""
        pass
    
    def testFailIfEntryPointIsNotFluxLike(self):
        """If any entry-point is a stock-like account, raise ``MalformedTransaction``"""
        pass
    
    def testFailIfTargetIsNotStockLike(self):
        """If any target account is not stock-like, raise ``MalformedTransaction``"""
        pass
        
    def testFailIfEntryPointAndTargetInDifferentAccountingSystems(self):
        """If, for a split, entry-point belongs to a different accounting system than target account, raise ``MalformedTransaction``"""
        pass


class RegisterTransactionTest(TestCase):
    """Check that the ``register_transaction()`` factory function works as advertised"""
   
    def setUp(self):
        pass
    
    def testTransactionCreationOK(self):
        """``register_transaction()`` should create a new transaction, based on given input"""
        pass
    
    def testLedgerEntriesCreationOK(self):
        """``register_transaction()`` should create implied ledger entries"""
        pass
    
    def testReturnValueIsTransaction(self):
        """``register_transaction()`` should return the newly created transaction"""
        pass
    
    def testFailIfSourceIsNotStockLike(self):
        """If source account is flux-like, raise ``MalformedTransaction``"""
        pass
    
    def testFailIfExitPointAndSourceInDifferentAccountingSystems(self):
        """If exit-point and source account belong to different accounting systems, raise ``MalformedTransaction``"""
        pass
    
    def testFailIfAnyIsPlaceholder(self):
        """If an involved account is a placeholder one, raise ``MalformedTransaction``"""
        pass   
    
    def testFailIfEntryOrExitPointNull(self):
        """If either entry-point or exit-point is ``None``,  raise ``MalformedTransaction``"""
        pass
    
    def testFailIfExitPointIsNotFluxLike(self):
        """If any exit-point is a stock-like account, raise ``MalformedTransaction``"""
        pass
    
    def testFailIfEntryPointIsNotFluxLike(self):
        """If any entry-point is a stock-like account, raise ``MalformedTransaction``"""
        pass
    
    def testFailIfTargetIsNotStockLike(self):
        """If any target account is not stock-like, raise ``MalformedTransaction``"""
        pass
        
    def testFailIfEntryPointAndTargetInDifferentAccountingSystems(self):
        """If entry-point belongs to a different accounting system than target account, raise ``MalformedTransaction``"""
        pass
    

class RegisterInternalTransactionTest(TestCase):
    """Check that the ``register_internal_transaction()`` factory function works as advertised"""
   
    def setUp(self):
        pass
    
    def testTransactionCreationOK(self):
        """``register_internal_transaction()`` should create a new transaction, based on given input"""
        pass
    
    def testLedgerEntriesCreationOK(self):
        """``register_internal_transaction()`` should create implied ledger entries"""
        pass
    
    def testReturnValueIsTransaction(self):
        """``register_internal_transaction()`` should return the newly created transaction"""
        pass
    
    def testFailIfSourceIsNotStockLike(self):
        """If source account is flux-like, raise ``MalformedTransaction``"""
        pass
    
    def testFailIfConservationOfMoneyNotSatisfied(self):
        """If *law of conservation of money* is not satisfied, raise ``MalformedTransaction``"""
        pass
    
    def testFailIfSourceAndTargetsInDifferentAccountingSystems(self):
        """If source and target accounts belong to different accounting systems, raise ``MalformedTransaction``"""
        pass
     
    def testFailIfAnyIsPlaceholder(self):
        """If an involved account is a placeholder one, raise ``MalformedTransaction``"""
        pass   
       
    def testFailIfTargetIsNotStockike(self):
        """If any target account is not stock-like, raise ``MalformedTransaction``"""
        pass
        
    
class RegisterSimpleTransactionTest(TestCase):
    """Check that the ``register_simple_transaction()`` factory function works as advertised"""
   
    def setUp(self):
        pass
    
    def testTransactionCreationOK(self):
        """``register_simple_transaction()`` should create a new transaction, based on given input"""
        pass
    
    def testLedgerEntriesCreationOK(self):
        """``register_simple_transaction()`` should create implied ledger entries"""
        pass
    
    def testReturnValueIsTransaction(self):
        """``register_simple_transaction()`` should return the newly created transaction"""
        pass
    
    def testFailIfSourceIsNotStockLike(self):
        """If source account is flux-like, raise ``MalformedTransaction``"""
        pass
    
    def testFailIfSourceAndTargetsInDifferentAccountingSystems(self):
        """If source and target accounts belong to different accounting systems, raise ``MalformedTransaction``"""
        pass
     
    def testFailIfAnyIsPlaceholder(self):
        """If an involved account is a placeholder one, raise ``MalformedTransaction``"""
        pass   
    
    def testFailIfTargetIsNotStockLike(self):
        """If target account is not stock-like, raise ``MalformedTransaction``"""
        pass
        
        
class UpdateTransactionTest(TestCase):
    """Check that the ``update_transaction()`` factory function works as advertised"""
   
    def setUp(self):
        pass
    
    def testTransactionUpdateOK(self):
        """``update_transaction()`` should update the given transaction, based on provided input"""
        pass
    
    def testStaleLedgerEntriesDeletionOK(self):
        """``update_transaction()`` should delete stale ledger entries"""
        pass
    
    def testUpdatedLedgerEntriesCreationOK(self):
        """``update_transaction()`` should create implied ledger entries"""
        pass
    
    def testReturnValueIsTransaction(self):
        """``update_transaction()`` should return the update transaction"""
        pass
    
    def testFailIfSourceIsNotStockLike(self):
        """If updated source account is flux-like, raise ``MalformedTransaction``"""
        pass
    
    def testFailIfConservationOfMoneyNotSatisfied(self):
        """If updated splits don't satisfy the *law of conservation of money*, raise ``MalformedTransaction``"""
        pass
    
    def testFailIfExitPointsAndSourceInDifferentAccountingSystems(self):
        """If updated exit-points and source account belong to different accounting systems, raise ``MalformedTransaction``"""
        pass
    
    def testFailIfSourceAndTargetsInDifferentAccountingSystemsAndInternal(self):
        """If updated transaction is internal and source and target accounts belong to different accounting systems, raise ``MalformedTransaction``"""
        pass
     
    def testFailIfAnyIsPlaceholder(self):
        """If an account involved by the updated transaction is a placeholder one, raise ``MalformedTransaction``"""
        pass   
    
    def testFailIfEntryExitPointNullStatusDiffers(self):
        """If, for an updated split, exit-point's and entry-point's null statuses are different, raise ``MalformedTransaction``"""
        pass
    
    def testFailIfExitPointIsNotFluxLike(self):
        """If any updated exit-point is a stock-like account, raise ``MalformedTransaction``"""
        pass
    
    def testFailIfEntryPointIsNotFluxLike(self):
        """If any updated entry-point is a stock-like account, raise ``MalformedTransaction``"""
        pass
    
    def testFailIfTargetIsNotStockike(self):
        """If any updated target account is not stock-like, raise ``MalformedTransaction``"""
        pass
        
    def testFailIfEntryPointAndTargetInDifferentAccountingSystems(self):
        """If, for an updated split, entry-point belongs to a different accounting system than target account, raise ``MalformedTransaction``"""
        pass    